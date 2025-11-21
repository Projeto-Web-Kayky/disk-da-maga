from django.urls import path
from .views import (
    ProductListView,
    ProductCreateView,
    ProductUpdateView,
    delete_product,
    search_products,
)

urlpatterns = [
    path('', ProductListView.as_view(), name='product_list'),
    path('search/', search_products, name='search_products'),
    path('create/', ProductCreateView.as_view(), name='product_create'),
    path(
        'update/<int:pk>/', ProductUpdateView.as_view(), name='product_update'
    ),
    path('delete/<int:pk>/', delete_product, name='product_delete'),
]
