from decimal import Decimal, InvalidOperation
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.http import HttpResponseBadRequest
from django.db import transaction
from django.db.models import Q, F
from .models import Sale, SaleItem
from products.models import Product
from clients.models import Client
from django.contrib.auth.decorators import login_required

@login_required
def sale_list(request):
    sales = Sale.objects.all().order_by('-created_at')
    return render(
        request,
        'sale_list.html',
        {'sales': sales, 'section_name': 'Lista de Vendas'},
    )

@login_required
def sale_create(request):
    clients = Client.objects.all()
    if request.method == 'POST':
        client_id = request.POST.get('client_id', '').strip()
        client_name = request.POST.get('client_name', '').strip()
        client = None
        if client_id:
            try:
                client = Client.objects.get(pk=int(client_id))
            except (Client.DoesNotExist, ValueError):
                client = None

        sale = Sale.objects.create(client=client, client_name=client_name)
        return render(
            request, 'partials/sale_created_feedback.html', {'sale': sale}
        )

    return render(
        request,
        'sale_create.html',
        {
            'clients': clients,
            'section_name': 'Cadastrar Nova Venda',
        },
    )


def _get_header_color_for_sale(sale):
    color_map = {
        'open': 'border-red-600 bg-red-100 text-red-900',
        'finalized': 'border-green-600 bg-green-100 text-green-900',
        'cancelled': 'border-gray-500 bg-gray-200 text-gray-700',
    }
    return color_map.get(
        sale.status, 'border-slate-600 bg-slate-100 text-slate-900'
    )


def sale_detail(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    header_color = _get_header_color_for_sale(sale)

    products = Product.objects.filter(quantity__gt=0).order_by('name')

    context = {
        'sale': sale,
        'products': products,
        'header_color': header_color,
        'section_name': 'Detalhes Da Comanda',
    }

    if request.headers.get('HX-Request') == 'true':
        return render(request, 'partials/sale_detail_fragment.html', context)

    return render(request, 'sale_detail.html', context)


def sale_header_fragment(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    return render(
        request, 'partials/sale_header_fragment.html', {'sale': sale}
    )


def pay_modal_fragment(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    return render(request, 'partials/modals/pay_modal.html', {'sale': sale})


@require_POST
def add_item(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)

    if sale.status != Sale.STATUS_OPEN:
        return HttpResponseBadRequest('Venda não está aberta.')

    product_id = (request.POST.get('product_id') or '').strip()
    quantity_raw = (request.POST.get('quantity') or '1').strip()

    if not product_id.isdigit():
        return HttpResponseBadRequest('ID de produto inválido.')

    try:
        quantity = int(quantity_raw)
        if quantity <= 0:
            return HttpResponseBadRequest('Quantidade inválida.')
    except ValueError:
        return HttpResponseBadRequest('Quantidade inválida.')

    with transaction.atomic():

        try:
            product = Product.objects.select_for_update().get(
                product_id=int(product_id)
            )
        except Product.DoesNotExist:
            return HttpResponseBadRequest('Produto não encontrado.')

        if product.quantity < quantity:
            return HttpResponseBadRequest('Estoque insuficiente.')

        sale_item = (
            SaleItem.objects.select_for_update()
            .filter(sale=sale, product=product)
            .first()
        )

        if sale_item:
            # Atualizar quantidade existente - o método save() do model vai gerenciar o estoque
            sale_item.quantity += quantity
            sale_item.save()
        else:
            # Criar novo item - o método save() do model vai gerenciar o estoque
            # Garantir que o preço tenha exatamente 2 casas decimais
            from decimal import Decimal
            price = Decimal(str(product.sale_price)).quantize(Decimal('0.01'))
            sale_item = SaleItem.objects.create(
                sale=sale,
                product=product,
                quantity=quantity,
                price=price,
            )

    sale.refresh_from_db()

    return render(request, 'partials/sale_items_fragment.html', {'sale': sale})


@require_POST
def remove_item(request, sale_id, item_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    if sale.status != Sale.STATUS_OPEN:
        return HttpResponseBadRequest('Venda não está aberta.')

    try:
        item = SaleItem.objects.get(pk=item_id, sale=sale)
    except SaleItem.DoesNotExist:
        return HttpResponseBadRequest('Item não encontrado.')

    with transaction.atomic():
        item.delete()

    sale.refresh_from_db()
    return render(request, 'partials/sale_items_fragment.html', {'sale': sale})


@require_POST
def pay_sale(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)

    if sale.status != Sale.STATUS_OPEN:
        return HttpResponseBadRequest('Venda não está aberta.')

    balance = sale.balance

    if balance <= 0:
        msg = (
            f'Não é possível realizar pagamento. Há um crédito de R$ {abs(balance):.2f} nesta comanda.'
            if balance < 0
            else 'Venda já está totalmente paga.'
        )
        return HttpResponseBadRequest(msg)

    amount_raw = request.POST.get('amount', '').strip()
    method = request.POST.get('method', '').strip()
    note = request.POST.get('note', '').strip()

    try:
        amount = Decimal(amount_raw)
    except InvalidOperation:
        return HttpResponseBadRequest('Valor inválido.')

    if amount <= 0:
        return HttpResponseBadRequest('Valor do pagamento deve ser positivo.')

    if amount > balance:
        return HttpResponseBadRequest(
            f'O valor informado (R$ {amount:.2f}) é maior que o saldo devido (R$ {balance:.2f}).'
        )

    try:
        sale.apply_payment(amount, method=method, note=note)
    except ValueError as e:
        return HttpResponseBadRequest(str(e))

    sale.refresh_from_db()

    return render(
        request,
        'partials/sale_items_fragment.html',
        {'sale': sale},
    )


def pix_qr(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)

    amount = request.GET.get('amount', '').strip()
    payload_parts = [f'PIX', f'sale:{sale.pk}']

    if amount:
        payload_parts.append(f'amount:{amount}')

    payload = '|'.join(payload_parts)

    context = {
        'sale': sale,
        'payload': payload,
        'amount': amount,
    }
    return render(request, 'partials/pix_qr.html', context)


def search_products(request, sale_id):
    query = (request.GET.get('search') or '').strip()
    sale = get_object_or_404(Sale, pk=sale_id)
    if query:
        products = Product.objects.filter(
            Q(name__icontains=query) & Q(quantity__gt=0) & Q(is_active=True)
        ).order_by('name')[:20]
    else:
        products = Product.objects.filter(
            quantity__gt=0, is_active=True
        ).order_by('name')[:20]

    return render(
        request,
        'partials/search_results_fragment.html',
        {'products': products, 'sale': sale},
    )


@require_POST
def cancel_sale(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    try:
        sale.cancel()
    except Exception as e:
        return HttpResponseBadRequest(str(e))
    products = Product.objects.filter(quantity__gt=0).order_by('name')
    return render(
        request,
        'partials/sale_detail_fragment.html',
        {'sale': sale, 'products': products},
    )


@require_POST
def reopen_sale(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    try:
        sale.reopen()
    except Exception as e:
        return HttpResponseBadRequest(str(e))
    products = Product.objects.filter(quantity__gt=0).order_by('name')
    return render(
        request,
        'partials/sale_detail_fragment.html',
        {'sale': sale, 'products': products},
    )


@require_POST
def delete_sale(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    with transaction.atomic():
        if sale.status == Sale.STATUS_FINALIZED:
            for item in sale.items.select_related('product'):
                item.product.quantity += item.quantity
                item.product.save(update_fields=['quantity'])
        sale.delete()
    return redirect('sale_list')
