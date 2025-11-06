from django.db import models
from django.utils import timezone

class Product(models.Model):
    class Category(models.TextChoices):
        SEM_CATEGORIA = 'SC', 'Sem Categoria'
        CERVEJA = 'CE', 'Cerveja'
        REFRIGERANTE = 'RE', 'Refrigerante'
        ENERGETICO = 'EN', 'Energético'
        PETISCOS = 'PE', 'Petiscos'
        ALIMENTOS = 'AL', 'Alimentos'
        WHISKY = 'WH', 'Whisky'
        VODKA = 'VO', 'Vodka'
        SUCOS = 'SU', 'Sucos'
        OUTROS = 'OU', 'Outros'

    product_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, blank=False, verbose_name='Nome')
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.SEM_CATEGORIA, verbose_name='Categoria')
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, null=False, blank=False, verbose_name='Preço de Venda')
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=False, blank=False, verbose_name='Preço de Custo')
    quantity = models.IntegerField(default=0, verbose_name='Quantidade')
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name='Data de Criação'
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name='Data de Atualização'
    )
    low_quantity = models.IntegerField(default=0, verbose_name='Estoque Baixo')

    def __str__(self):
        return self.name