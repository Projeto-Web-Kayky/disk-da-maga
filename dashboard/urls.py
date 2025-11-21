from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path(
        'dados-relatorio/',
        views.generate_report_data,
        name='generate_report_data',
    ),
    path(
        'gerar-relatorio/',
        views.generate_report_pdf,
        name='generate_report_pdf',
    ),
]
