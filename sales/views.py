from decimal import Decimal, InvalidOperation
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.http import HttpResponseBadRequest
from django.db import transaction
from .models import Sale, SaleItem
from products.models import Product
from clients.models import Client

def sale_list(request):
    sales = Sale.objects.all().order_by('-created_at')
    return render(request, 'sale_list.html', {'sales': sales, 'section_name': 'Vendas'})

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
        return render(request, 'partials/sale_created_feedback.html', {'sale': sale})

    return render(request, 'sale_create.html', {'clients': clients, 'section_name': 'Nova Venda'})

def sale_detail(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    products = Product.objects.filter(quantity__gt=0).order_by('name')
    return render(request, 'sale_detail.html', {'sale': sale, 'products': products, 'section_name': 'Comanda'})

@require_POST
def add_item(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    if sale.status != Sale.STATUS_OPEN:
        return HttpResponseBadRequest("Venda não está aberta.")

    product_id = request.POST.get('product_id', '').strip()
    quantity_raw = request.POST.get('quantity', '1').strip() or '1'
    try:
        quantity = int(quantity_raw)
        if quantity <= 0:
            raise ValueError()
    except ValueError:
        return HttpResponseBadRequest("Quantidade inválida.")

    if not product_id:
        return HttpResponseBadRequest("Produto não informado.")

    try:
        product = Product.objects.get(pk=int(product_id))
    except (Product.DoesNotExist, ValueError):
        return HttpResponseBadRequest("Produto inválido.")

    with transaction.atomic():
        item, created = SaleItem.objects.select_for_update().get_or_create(
            sale=sale,
            product=product,
            defaults={'quantity': quantity, 'price': product.sale_price}
        )
        if not created:
            item.quantity += quantity
            item.save(update_fields=['quantity'])
    return render(request, 'partials/sale_items_fragment.html', {'sale': sale})

@require_POST
def pay_sale(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    if sale.status != Sale.STATUS_OPEN:
        return HttpResponseBadRequest("Venda não está aberta.")

    amount_raw = request.POST.get('amount', '').strip()
    method = request.POST.get('method', '').strip()
    note = request.POST.get('note', '').strip()

    try:
        amount = Decimal(amount_raw)
    except (InvalidOperation, TypeError):
        return HttpResponseBadRequest("Valor inválido.")

    try:
        sale.apply_payment(amount, method=method, note=note)
    except ValueError as e:
        return HttpResponseBadRequest(str(e))

    return render(request, 'partials/sale_payment_fragment.html', {'sale': sale})

@require_POST
def cancel_sale(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    try:
        sale.cancel()
    except Exception as e:
        return HttpResponseBadRequest(str(e))
    return render(request, 'sale_detail.html', {'sale': sale, 'products': Product.objects.filter(quantity__gt=0)})

@require_POST
def reopen_sale(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    try:
        sale.reopen()
    except Exception as e:
        return HttpResponseBadRequest(str(e))
    return render(request, 'sale_detail.html', {'sale': sale, 'products': Product.objects.filter(quantity__gt=0)})

@require_POST
def remove_item(request, sale_id, item_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    if sale.status != Sale.STATUS_OPEN:
        return HttpResponseBadRequest("Venda não está aberta.")

    try:
        item = SaleItem.objects.get(pk=item_id, sale=sale)
    except SaleItem.DoesNotExist:
        return HttpResponseBadRequest("Item não encontrado.")

    with transaction.atomic():
        item.delete()

    return render(request, 'partials/sale_items_fragment.html', {'sale': sale})
