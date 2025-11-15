from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, CreateView, UpdateView
from products.models import Product
from products.forms import ProductForm
from django.http import HttpRequest
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import F


class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'product_list.html'
    context_object_name = 'products'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['section_name'] = 'Estoque de Produtos'
        return context

    def get_queryset(self):
        # 🔹 Exibir apenas produtos ativos
        return Product.objects.filter(is_active=True)


class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'product_form.html'
    success_url = '/products/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['section_name'] = 'Cadastro de Produto'
        return context


class ProductUpdateView(LoginRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'product_update.html'
    success_url = '/products/'


@login_required
def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)

    if request.method == 'POST':
        # Soft delete
        product.is_active = False
        product.save()

        return redirect('product_list')

    return render(request, 'product_delete.html', {'object': product})


@login_required
def search_products(request: HttpRequest):
    search = request.GET.get('search', '')
    filter_option = request.GET.get('filter', '')

    # 🔹 Mostra apenas produtos ativos
    products = Product.objects.filter(is_active=True)

    if search:
        products = products.filter(name__icontains=search)

    if filter_option == 'estoque_baixo':
        products = products.filter(quantity__lte=F('low_quantity'))
    elif filter_option == 'estoque_normal':
        products = products.filter(quantity__gt=F('low_quantity'))
    elif filter_option == 'maior_preco':
        products = products.order_by('-sale_price')
    elif filter_option == 'menor_preco':
        products = products.order_by('sale_price')

    context = {'products': products}

    return render(request, 'partials/_product_table.html', context)
