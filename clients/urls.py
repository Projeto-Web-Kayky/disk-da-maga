from django.urls import path
from .views import client_list, client_detail, client_delete, client_edit

urlpatterns = [
    path("", client_list, name="client_list"),
    path("<int:client_id>/", client_detail, name="client_detail"),
    path("<int:client_id>/delete/", client_delete, name="client_delete"),
    path("<int:client_id>/edit/", client_edit, name="client_edit"),
]
