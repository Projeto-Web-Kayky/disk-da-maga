from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, DetailView, View
from django.http import JsonResponse
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from .models import Sale, Product, SaleItem
from .forms import SaleForm
import json

class SaleListView(LoginRequiredMixin, ListView):
    model = Sale
    template_name = "sale_list.html"
    context_object_name = "sales"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section_name"] = "Vendas"
        return context


class SaleCreateView(LoginRequiredMixin, View):
    template_name = "sale_form.html"

    def get(self, request):
        context = {
            "section_name": "Nova Venda"
        }
        return render(request, self.template_name, context)

    def post(self, request):
        try:
            data = json.loads(request.body)
            product_ids = data.get('product_ids', [])
            quantities = data.get('quantities', [])
            payment_method = data.get('payment_method')
            client_id = data.get('client_id')

            if not product_ids or not quantities:
                return JsonResponse({
                    'success': False,
                    'message': 'Produtos e quantidades são obrigatórios'
                }, status=400)

            # Criar a venda
            sale = Sale.objects.create(
                client_id=client_id,
                payment_method=payment_method,
                total=0
            )

            total = 0
            # Criar os itens da venda
            for product_id, quantity in zip(product_ids, quantities):
                product = Product.objects.get(id=product_id)
                subtotal = product.sale_price * quantity
                total += subtotal

                SaleItem.objects.create(
                    sale=sale,
                    product=product,
                    quantity=quantity,
                    unit_price=product.sale_price,
                    subtotal=subtotal
                )

            # Atualizar o total da venda
            sale.total = total
            sale.save()

            return JsonResponse({
                'success': True,
                'message': 'Venda registrada com sucesso!',
                'sale_id': sale.id
            })

        except Product.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Produto não encontrado'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)


class ProductSearchView(LoginRequiredMixin, View):
    def get(self, request):
        query = request.GET.get('q', '')
        
        if len(query) < 2:
            return JsonResponse({'data': []})

        products = Product.objects.filter(
            Q(product_name__icontains=query) | 
            Q(code__icontains=query)
        ).values('id', 'product_name', 'sale_price', 'code')[:10]

        return JsonResponse({
            'data': list(products)
        })


class SaleDetailView(DetailView):
    model = Sale
    template_name = "sale_detail.html"
    context_object_name = "sale"