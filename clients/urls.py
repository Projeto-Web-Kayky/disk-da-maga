from django.urls import path
from .views import client_delete, client_list, client_detail, client_delete, client_edit, client_clear_debts

urlpatterns = [
    path('', client_list, name='client_list'),
    path('<int:client_id>/', client_detail, name='client_detail'),
    path('<int:client_id>/delete-modal/', client_delete, name='client_delete_modal'),
    path('<int:client_id>/delete/', client_delete, name='client_delete'),
    path('<int:client_id>/edit/', client_edit, name='client_edit'),
    path('<int:client_id>/clear-debts/', client_clear_debts, name='client_clear_debts'),
]