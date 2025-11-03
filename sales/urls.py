from django.urls import path
from .views import SaleListView, SaleCreateView

urlpatterns = [
    path('', SaleListView.as_view(), name='sale_list'),
    path('create/', SaleCreateView.as_view(), name='sale_create'),
]