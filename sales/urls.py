from django.urls import path
from . import views

urlpatterns = [
    path('', views.sale_list, name='sale_list'),
    path('create/', views.sale_create, name='sale_create'),
    path('<int:sale_id>/', views.sale_detail, name='sale_detail'),
    path('<int:sale_id>/add-item/', views.add_item, name='add_item'),
    path('<int:sale_id>/pay/', views.pay_sale, name='pay_sale'),
    path('<int:sale_id>/cancel/', views.cancel_sale, name='cancel_sale'),
    path('<int:sale_id>/reopen/', views.reopen_sale, name='reopen_sale'),
    path('<int:sale_id>/delete/', views.delete_sale, name='delete_sale'),
    path('sales/<int:sale_id>/remove-item/<int:item_id>/', views.remove_item, name='remove_item'),
]
