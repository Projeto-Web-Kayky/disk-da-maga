from decimal import Decimal
from django.db import models, transaction
from django.db.models import F, Sum


class Sale(models.Model):
    STATUS_OPEN = 'open'
    STATUS_FINALIZED = 'finalized'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Aberta'),
        (STATUS_FINALIZED, 'Finalizada'),
        (STATUS_CANCELLED, 'Cancelada'),
    ]

    client = models.ForeignKey(
        'clients.Client',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='sales',
    )
    client_name = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        who = (
            self.client.name
            if self.client
            else (self.client_name or 'Cliente Avulso')
        )
        return f'Venda #{self.pk} - {who} - {self.status}'

    @property
    def total(self):
        agg = self.items.aggregate(total=Sum(F('price') * F('quantity')))
        return agg['total'] or Decimal('0.00')

    @property
    def paid_amount(self):
        agg = self.payments.aggregate(total=Sum('amount'))
        return agg['total'] or Decimal('0.00')

    @property
    def balance(self):
        return (self.total - self.paid_amount).quantize(Decimal('0.01'))

    def get_client_display(self):
        return self.client.name if self.client else self.client_name

    def update_client_debt_cache(self):
        if not self.client:
            return
        debt = Sale.objects.filter(
            client=self.client, status=self.STATUS_OPEN
        ).aggregate(total=Sum(F('items__price') * F('items__quantity')))[
            'total'
        ] or Decimal(
            '0.00'
        )
        paid = Sale.objects.filter(
            client=self.client, status=self.STATUS_OPEN
        ).aggregate(paid=Sum('payments__amount'))['paid'] or Decimal('0.00')
        self.client.client_debts = (debt - paid).quantize(Decimal('0.01'))
        self.client.save(update_fields=['client_debts'])

    def finalize_and_reserve_stock(self):
        if self.status != self.STATUS_OPEN:
            return
        with transaction.atomic():
            sale_locked = Sale.objects.select_for_update().get(pk=self.pk)
            for item in sale_locked.items.select_related('product'):
                if item.product.quantity < item.quantity:
                    raise ValueError(
                        f'Estoque insuficiente para {item.product.name} '
                        f'({item.product.quantity} disponível, {item.quantity} solicitado).'
                    )
            for item in sale_locked.items.select_related('product'):
                item.product.quantity -= item.quantity
                item.product.save(update_fields=['quantity'])
            sale_locked.status = self.STATUS_FINALIZED
            sale_locked.save(update_fields=['status', 'updated_at'])
            sale_locked.update_client_debt_cache()

    def cancel(self):
        if self.status == self.STATUS_CANCELLED:
            return
        with transaction.atomic():
            for item in self.items.select_related('product'):
                item.product.quantity += item.quantity
                item.product.save(update_fields=['quantity'])
            self.status = self.STATUS_CANCELLED
            self.save(update_fields=['status', 'updated_at'])
            self.update_client_debt_cache()

    def reopen(self):
        if self.status not in [self.STATUS_CANCELLED, self.STATUS_FINALIZED]:
            return
        with transaction.atomic():
            if self.status == self.STATUS_FINALIZED:
                # Return reserved stock
                for item in self.items.select_related('product'):
                    item.product.quantity += item.quantity
                    item.product.save(update_fields=['quantity'])
            self.status = self.STATUS_OPEN
            self.save(update_fields=['status', 'updated_at'])
            self.update_client_debt_cache()

    def apply_payment(self, amount, method=None, note=None):
        if amount <= 0:
            raise ValueError('Valor do pagamento deve ser positivo.')
        with transaction.atomic():
            sale_locked = Sale.objects.select_for_update().get(pk=self.pk)
            Payment.objects.create(
                sale=sale_locked, amount=amount, method=method, note=note
            )
            
            if method == 'fiado' and sale_locked.client:
                sale_locked.client.client_debts += amount
                sale_locked.client.save(update_fields=['client_debts'])
            
            if sale_locked.paid_amount >= sale_locked.total:
                sale_locked.finalize_and_reserve_stock()
            else:
                sale_locked.update_client_debt_cache()


class SaleItem(models.Model):
    sale = models.ForeignKey(
        Sale, on_delete=models.CASCADE, related_name='items'
    )
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        unique_together = ('sale', 'product')

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'

    def save(self, *args, **kwargs):
        with transaction.atomic():
            creating = self.pk is None
            if not creating:
                old = SaleItem.objects.select_for_update().get(pk=self.pk)
                diff = self.quantity - old.quantity
            else:
                diff = self.quantity

            super().save(*args, **kwargs)
            if creating or diff > 0:
                to_sub = diff if not creating else self.quantity
                self.product.quantity = max(self.product.quantity - to_sub, 0)
            elif diff < 0:
                self.product.quantity += abs(diff)
            self.product.save(update_fields=['quantity'])

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            self.product.quantity += self.quantity
            self.product.save(update_fields=['quantity'])
            super().delete(*args, **kwargs)


class Payment(models.Model):
    sale = models.ForeignKey(
        Sale, related_name='payments', on_delete=models.CASCADE
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=50, null=True, blank=True)
    note = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'R${self.amount} - Venda #{self.sale_id}'
