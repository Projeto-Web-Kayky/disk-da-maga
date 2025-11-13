from . import views
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from accounts.views import login_view, logout_view
from clients.views import client_list, client_detail, client_delete
from products.views import (
    ProductListView,
    ProductCreateView,
    ProductUpdateView,
    delete_product,
    search_products,
)

urlpatterns = [
    path('base/', views.base_view, name='base_view'),
    path('admin/', admin.site.urls),
    path('', login_view, name='login'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('products/', ProductListView.as_view(), name='product_list'),
    path('products/search/', search_products, name='search_products'),
    path(
        'products/create/', ProductCreateView.as_view(), name='product_create'
    ),
    path(
        'products/update/<int:pk>/',
        ProductUpdateView.as_view(),
        name='product_update',
    ),
    path(
        'products/delete/<int:pk>/',
        delete_product,
        name='product_delete',
    ),
    path('clients/', client_list, name='client_list'),
    path('clients/<int:client_id>/', client_detail, name='client_detail'),
    path('clients/<int:client_id>/delete/', client_delete, name='client_delete'),
    path('sales/', include('sales.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
