from django.db import models
from products.models import Product

class Sale(models.Model):
    sale_date = models.DateTimeField(auto_now_add=True)
    products = models.ManyToManyField(Product, through='SaleItem')
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Venda {self.id}"
    
class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
