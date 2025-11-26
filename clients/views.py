from django.shortcuts import render, redirect, get_object_or_404
from clients.models import Client
from clients.forms import ClientForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponse, HttpResponseBadRequest
import json


@login_required
def client_list(request):
    clients = Client.objects.all()
    form = ClientForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        client = form.save(commit=False)
        # Se o cliente está sendo criado (não tem pk) e tem dívida cadastrada,
        # copiar para initial_debt
        if not client.pk and client.client_debts:
            client.initial_debt = client.client_debts
            client.client_debts = client.initial_debt
        client.save()
        return redirect('client_list')

    return render(
        request,
        'client_list.html',
        {
            'clients': clients,
            'form': form,
            'section_name': 'Lista de Clientes',
        },
    )


@login_required
def client_detail(request, client_id):
    """Render client detail modal fragment."""
    from sales.models import Payment
    from django.db.models import Sum
    from decimal import Decimal
    
    client = get_object_or_404(Client, pk=client_id)
    
    # Calcular total de pagamentos fiados (sem a dívida inicial)
    total_fiado = Payment.objects.filter(
        sale__client=client,
        method__iexact='fiado'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    context = {
        'client': client,
        'total_fiado': total_fiado,  # Apenas pagamentos fiados (sem dívida inicial)
    }
    return render(
        request, 'partials/client_detail_modal.html', context
    )

@login_required
def client_delete(request, client_id):
    client = get_object_or_404(Client, pk=client_id) 
    return render(request, 'partials/client_delete_modal.html', {
        'client': client
    })


@login_required
def client_edit(request, client_id):
    client = get_object_or_404(Client, pk=client_id)
    is_htmx = request.headers.get('Hx-Request') == 'true'

    if request.method == 'POST':
        form = ClientForm(request.POST, request.FILES, instance=client)

        if form.is_valid():
            form.save()

            if is_htmx:
                # 204 diz ao HTMX para não trocar o conteúdo,
                # e HX-Refresh força reload (caso você realmente queira isso).
                return HttpResponse(status=204, headers={'HX-Refresh': 'true'})

            return redirect('client_list')

        # Form inválido → apenas renderizar com status correto
        status_code = 422 if is_htmx else 200
        return render(
            request,
            'partials/client_edit_modal.html',
            {'form': form, 'client': client},
            status=status_code,
        )

    # GET
    form = ClientForm(instance=client)
    return render(
        request,
        'partials/client_edit_modal.html',
        {'form': form, 'client': client},
    )


@login_required
@require_POST
def client_delete(request, client_id):
    client = get_object_or_404(Client, pk=client_id)
    is_htmx = request.headers.get('Hx-Request') == 'true'

    try:
        client.delete()
    except Exception as e:
        return HttpResponseBadRequest(str(e))

    if is_htmx:
        # Retornar resposta vazia com trigger para remover o cliente da lista
        response = HttpResponse(status=200)
        response['HX-Trigger'] = json.dumps(
            {'clientDeleted': {'clientId': client_id}}
        )
        return response
    
    return redirect('client_list')


@login_required
@require_POST
def client_clear_debts(request, client_id):
    """Quita dívidas do cliente (pagamentos fiados e/ou dívida inicial)"""
    from decimal import Decimal, InvalidOperation
    from django.db import transaction
    from sales.models import Payment, Sale
    
    client = get_object_or_404(Client, pk=client_id)
    is_htmx = request.headers.get('Hx-Request') == 'true'
    
    # Obter valor a quitar (opcional)
    amount_raw = request.POST.get('amount', '').strip()
    amount_to_clear = None
    
    if amount_raw:
        try:
            amount_to_clear = Decimal(amount_raw).quantize(Decimal('0.01'))
            if amount_to_clear <= 0:
                return HttpResponseBadRequest('Valor deve ser maior que zero.')
        except (InvalidOperation, ValueError):
            return HttpResponseBadRequest('Valor inválido.')
    
    with transaction.atomic():
        # Buscar todos os pagamentos fiados do cliente (ordenados por data, mais antigos primeiro)
        payments_fiado = Payment.objects.filter(
            sale__client=client,
            method__iexact='fiado'
        ).order_by('created_at')
        
        # Calcular o total de pagamentos fiados
        from django.db.models import Sum
        total_fiado = payments_fiado.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        total_fiado = total_fiado.quantize(Decimal('0.01'))
        
        # Obter dívida inicial
        divida_inicial = client.initial_debt or Decimal('0.00')
        divida_inicial = divida_inicial.quantize(Decimal('0.01'))
        
        # Calcular dívida total
        divida_total = (divida_inicial + total_fiado).quantize(Decimal('0.01'))
        
        if amount_to_clear is None:
            # Se não informou valor, quitar toda a dívida (fiados + inicial)
            amount_to_clear = divida_total
        else:
            # Verificar se o valor não excede a dívida total
            if amount_to_clear > divida_total:
                return HttpResponseBadRequest(
                    f'O valor informado (R$ {amount_to_clear:.2f}) é maior que a dívida total (R$ {divida_total:.2f}).'
                )
        
        # Quitar pagamentos fiados primeiro (começando pelos mais antigos)
        remaining = amount_to_clear.quantize(Decimal('0.01'))
        
        # Se houver pagamentos fiados, quitá-los primeiro
        if payments_fiado.exists():
            for payment in payments_fiado:
                if remaining <= 0:
                    break
                
                if payment.amount <= remaining:
                    # Quitar o pagamento inteiro
                    payment.method = 'quitado'
                    payment.save(update_fields=['method'])
                    remaining -= payment.amount
                    remaining = remaining.quantize(Decimal('0.01'))
                else:
                    # Quitar parcialmente: dividir o pagamento
                    # Criar um novo pagamento quitado com o valor a quitar
                    Payment.objects.create(
                        sale=payment.sale,
                        amount=remaining,
                        method='quitado',
                        note=f'Quitação parcial (original: R$ {payment.amount})'
                    )
                    # Reduzir o valor do pagamento original (que continua fiado)
                    payment.amount -= remaining
                    payment.amount = payment.amount.quantize(Decimal('0.01'))
                    payment.save(update_fields=['amount'])
                    remaining = Decimal('0.00')
        
        # Se ainda sobrar valor, quitar da dívida inicial
        valor_quitado_divida_inicial = Decimal('0.00')
        if remaining > 0 and divida_inicial > 0:
            # Calcular quanto da dívida inicial será quitado
            valor_quitado_divida_inicial = min(remaining, divida_inicial)
            
            nova_divida_inicial = max(Decimal('0.00'), divida_inicial - remaining)
            nova_divida_inicial = nova_divida_inicial.quantize(Decimal('0.01'))
            client.initial_debt = nova_divida_inicial
            client.save(update_fields=['initial_debt'])
            
            # Registrar quitação da dívida inicial (sem criar venda)
            # Isso permitirá que o valor seja contabilizado nas vendas do mês
            if valor_quitado_divida_inicial > 0:
                from clients.models import DebtPayment
                
                # Criar registro de quitação
                DebtPayment.objects.create(
                    client=client,
                    amount=valor_quitado_divida_inicial,
                    note=f'Quitação de dívida inicial'
                )
        
        # Recalcular a dívida (agora será initial_debt + pagamentos fiados restantes)
        sales = Sale.objects.filter(client=client)
        
        # Se houver vendas, atualizar via update_client_debt_cache
        if sales.exists():
            for sale in sales:
                sale.update_client_debt_cache()
        else:
            # Se não houver vendas, atualizar client_debts diretamente
            # Recarregar o cliente para garantir que initial_debt está atualizado
            client.refresh_from_db()
            
            # Recalcular total de pagamentos fiados restantes
            pagamentos_fiado_restantes = Payment.objects.filter(
                sale__client=client,
                method__iexact='fiado'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            pagamentos_fiado_restantes = pagamentos_fiado_restantes.quantize(Decimal('0.01'))
            
            # Atualizar client_debts = initial_debt + pagamentos fiados restantes
            nova_divida_total = (client.initial_debt + pagamentos_fiado_restantes).quantize(Decimal('0.01'))
            client.client_debts = nova_divida_total
            client.save(update_fields=['client_debts'])
        
        client.refresh_from_db()

        from django.db.models import Sum
        total_fiado = Payment.objects.filter(
            sale__client=client,
            method__iexact='fiado'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    if is_htmx:
        # Recarregar o cliente para garantir dados atualizados
        client.refresh_from_db()
        # Retornar o modal atualizado com trigger para atualizar dashboard
        response = render(
            request,
            'partials/client_detail_modal.html',
            {
                'client': client,
                'total_fiado': total_fiado
            }
        )
        response['HX-Trigger'] = json.dumps({
            'debtsCleared': {'clientId': client_id},
            'refreshDashboard': {}
        })
        return response
    
    return redirect('client_list')