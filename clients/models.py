from django.db import models


class Client(models.Model):
    client_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, blank=False, verbose_name='Nome')
    nickname = models.CharField(
        max_length=100, blank=True, verbose_name='Apelido'
    )
    phone_number = models.CharField(
        max_length=20, blank=False, verbose_name='Telefone'
    )
    client_debts = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name='Dívidas do Cliente',
    )
    photo = models.ImageField(
        upload_to='client_photos/', verbose_name='Foto do Cliente'
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name='Data de Criação'
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name='Data de Atualização'
    )

    def __str__(self):
        return self.name
