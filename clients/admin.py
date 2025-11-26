from django.contrib import admin
from .models import Client, DebtPayment


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone_number', 'client_debts', 'initial_debt', 'created_at']
    search_fields = ['name', 'nickname', 'phone_number']
    list_filter = ['created_at']


@admin.register(DebtPayment)
class DebtPaymentAdmin(admin.ModelAdmin):
    list_display = ['client', 'amount', 'created_at', 'note']
    list_filter = ['created_at']
    search_fields = ['client__name', 'note']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at']
