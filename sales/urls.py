from django.urls import path
from . import views


urlpatterns = [
    path('', views.sale_list, name='sale_list'),
    path('create/', views.sale_create, name='sale_create'),
    path('<int:sale_id>/', views.sale_detail, name='sale_detail'),
    path('<int:sale_id>/add-item/', views.add_item, name='add_item'),
    path('<int:sale_id>/pay/', views.pay_sale, name='pay_sale'),
    path('<int:sale_id>/pix-qr/', views.pix_qr, name='sale_pix_qr'),
    path('<int:sale_id>/remove-item/<int:item_id>/', views.remove_item, name='remove_item'),
    path('<int:sale_id>/search-products/', views.search_products, name='search_products'),
]
