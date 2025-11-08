from django.contrib import admin
from .models import Sale, SaleItem, Payment


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ('price',)


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ('amount', 'method', 'created_at')


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'get_client',
        'status',
        'total',
        'paid_amount',
        'balance',
        'created_at',
    )
    inlines = [SaleItemInline, PaymentInline]
    readonly_fields = ('created_at', 'updated_at')

    def get_client(self, obj):
        return obj.get_client_display()

    get_client.short_description = 'Cliente'
