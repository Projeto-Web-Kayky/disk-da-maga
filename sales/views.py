from decimal import Decimal, InvalidOperation
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import HttpResponseBadRequest
from django.db import transaction
from .models import Sale, SaleItem
from products.models import Product
from clients.models import Client
from django.db.models import Q


def sale_list(request):
    sales = Sale.objects.all().order_by('-created_at')
    return render(
        request, 'sale_list.html', {'sales': sales, 'section_name': 'Vendas'}
    )


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
        {'clients': clients, 'section_name': 'Nova Venda'},
    )


def sale_detail(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)

    color_map = {
        'open': 'border-red-600 bg-red-100 text-red-900',
        'finalized': 'border-green-600 bg-green-100 text-green-900',
        'cancelled': 'border-gray-500 bg-gray-200 text-gray-700',
    }
    header_color = color_map.get(sale.status, 'border-slate-600 bg-slate-100 text-slate-900')

    products = Product.objects.filter(quantity__gt=0).order_by('name')

    context = {
        'sale': sale,
        'products': products,
        'header_color': header_color,
    }

    if request.headers.get('HX-Request') == 'true':
        # 🔥 Inclui o contexto completo, inclusive products!
        return render(request, 'partials/sale_detail_fragment.html', context)

    return render(request, 'sale_detail.html', context)


@require_POST
def add_item(request, sale_id):
    print("POST DATA:", request.POST)
    sale = get_object_or_404(Sale, pk=sale_id)

    if sale.status != Sale.STATUS_OPEN:
        return HttpResponseBadRequest('Venda não está aberta.')

    product_id = request.POST.get('product_id')
    quantity_raw = request.POST.get('quantity', '1')

    if not product_id or not product_id.isdigit():
        return HttpResponseBadRequest('ID de produto inválido.')

    try:
        quantity = int(quantity_raw)
        if quantity <= 0:
            return HttpResponseBadRequest('Quantidade inválida.')
    except ValueError:
        return HttpResponseBadRequest('Quantidade inválida.')

    try:
        product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist:
        return HttpResponseBadRequest('Produto não encontrado.')

    if product.quantity < quantity:
        return HttpResponseBadRequest('Estoque insuficiente.')

    with transaction.atomic():
        SaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=quantity,
            price=product.sale_price,
        )

        product.quantity -= quantity
        product.save()

    sale.refresh_from_db()
    return render(request, 'partials/sale_items_fragment.html', {'sale': sale})


@require_POST
def pay_sale(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    if sale.status != Sale.STATUS_OPEN:
        return HttpResponseBadRequest('Venda não está aberta.')

    amount_raw = request.POST.get('amount', '').strip()
    method = request.POST.get('method', '').strip()
    note = request.POST.get('note', '').strip()

    try:
        amount = Decimal(amount_raw)
    except (InvalidOperation, TypeError):
        return HttpResponseBadRequest('Valor inválido.')

    try:
        sale.apply_payment(amount, method=method, note=note)
    except ValueError as e:
        return HttpResponseBadRequest(str(e))

    return render(
        request,
        'partials/sale_payment_fragment.html',
        {
            'sale': sale,
            'close_modal': True,
        },
    )


@require_POST
def cancel_sale(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    try:
        sale.cancel()
    except Exception as e:
        return HttpResponseBadRequest(str(e))
    return render(
        request,
        'sale_detail.html',
        {'sale': sale, 'products': Product.objects.filter(quantity__gt=0)},
    )


@require_POST
def reopen_sale(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    try:
        sale.reopen()
    except Exception as e:
        return HttpResponseBadRequest(str(e))
    return render(
        request,
        'sale_detail.html',
        {'sale': sale, 'products': Product.objects.filter(quantity__gt=0)},
    )


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


def search_products(request, sale_id):
    query = request.GET.get('search', '').strip()
    sale = get_object_or_404(Sale, pk=sale_id)

    if query:
        products = Product.objects.filter(Q(name__icontains=query)).order_by('name')[:20]
    else:
        # lista inicial quando não há busca
        products = Product.objects.filter(quantity__gt=0).order_by('name')[:20]

    return render(
        request,
        'partials/search_results_fragment.html',
        {
            'products': products,
            'sale': sale,
        },
    )
