from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views import View
from django.views.generic import ListView, CreateView, DeleteView, UpdateView
from products.models import Product
from products.forms import ProductForm
from django.http import HttpRequest
from django.shortcuts import render


class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'product_list.html'
    context_object_name = 'products'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['section_name'] = 'Estoque de Produtos'
        return context


class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'product_form.html'
    success_url = '/products/'


class ProductUpdateView(LoginRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'product_update.html'
    success_url = '/products/'


class ProductDeleteView(LoginRequiredMixin, DeleteView):
    model = Product
    template_name = 'product_delete.html'
    success_url = '/products/'

    def get(self, request, *args, **kwargs):
        """Retorna modal"""
        self.object = self.get_object()
        return render(request, self.template_name, {'object': self.object})

    def delete(self, request, *args, **kwargs):
        """Exclui e atualiza a tabela via HTMX"""
        self.object = self.get_object()
        self.object.delete()
        products = Product.objects.all()
        return render(request, 'partials/_product_table.html', {'products': products})

@login_required
def search_products(request: HttpRequest):
    search = request.GET.get('search', '')
    filter_option = request.GET.get('filter', '')

    products = Product.objects.all()

    if search:
        products = products.filter(name__icontains=search)

    if filter_option == 'estoque_baixo':
        products = products.order_by('quantity')
    elif filter_option == 'estoque_alto':
        products = products.order_by('-quantity')
    elif filter_option == 'maior_preco':
        products = products.order_by('-sale_price')
    elif filter_option == 'menor_preco':
        products = products.order_by('sale_price')

    context = {'products': products}

    return render(request, 'partials/_product_table.html', context)
