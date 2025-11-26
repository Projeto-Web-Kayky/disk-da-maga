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
    initial_debt = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name='Dívida Inicial',
        help_text='Dívida cadastrada manualmente ao criar o cliente (não vem de pagamentos fiados)',
    )
    photo = models.ImageField(
        upload_to='client_photos/',
        verbose_name='Foto do Cliente',
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name='Data de Criação'
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name='Data de Atualização'
    )

    def __str__(self):
        return self.name


class DebtPayment(models.Model):
    """Registra quitações de dívidas iniciais dos clientes"""
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='debt_payments',
        verbose_name='Cliente'
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Valor Quitado'
    )
    note = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Observação'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data da Quitação'
    )

    class Meta:
        verbose_name = 'Quitação de Dívida'
        verbose_name_plural = 'Quitações de Dívidas'
        ordering = ['-created_at']

    def __str__(self):
        return f'R$ {self.amount} - {self.client.name} - {self.created_at.strftime("%d/%m/%Y")}'