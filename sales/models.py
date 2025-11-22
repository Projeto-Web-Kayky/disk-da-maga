from decimal import Decimal
from django.db import models, transaction
from django.db.models import F, Sum, Q
from django.db.models.functions import Coalesce


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
        total = agg['total'] or Decimal('0.00')
        # Garantir que o total tenha exatamente 2 casas decimais
        return total.quantize(Decimal('0.01'))

    @property
    def paid_amount(self):
        agg = self.payments.aggregate(total=Sum('amount'))
        paid = agg['total'] or Decimal('0.00')
        # Garantir que o valor pago tenha exatamente 2 casas decimais
        return paid.quantize(Decimal('0.01'))

    @property
    def balance(self):
        return (self.total - self.paid_amount).quantize(Decimal('0.01'))

    @property
    def credit_amount(self):
        """Retorna o valor do crédito (saldo negativo) como valor positivo"""
        balance = self.balance
        return abs(balance) if balance < 0 else Decimal('0.00')

    def get_client_display(self):
        return self.client.name if self.client else self.client_name

    def update_client_debt_cache(self):
        """
        Recalcula e atualiza a dívida do cliente.

        A dívida do cliente é SIMPLESMENTE a soma de todos os pagamentos fiados
        que ele fez em TODAS as vendas (abertas e finalizadas).

        Pagamentos fiados são dívidas que o cliente deve pagar depois.
        Não importa se a venda está aberta ou finalizada, o pagamento fiado
        sempre aumenta a dívida do cliente.

        Exemplo:
        - Venda de 7 reais
        - Pagamento de 6 reais no PIX (não-fiado) - não afeta a dívida
        - Pagamento de 1 real fiado (conta do cliente) - aumenta a dívida em 1
        - Dívida = 1 real (apenas o pagamento fiado)

        IMPORTANTE: Este método SEMPRE recalcula do zero, substituindo o valor atual.
        Isso garante que não há duplicação.
        """
        if not self.client:
            return

        Payment = self.payments.model

        # Calcular APENAS a soma de todos os pagamentos fiados (não quitados)
        # Pagamentos fiados são dívidas que o cliente deve pagar
        # Quando quitados, o método é alterado de "fiado" para "quitado", então não são mais contabilizados
        # Não importa o status da venda, pagamentos fiados sempre aumentam a dívida
        
        # Buscar todos os pagamentos fiados do cliente (apenas método exatamente "fiado")
        pagamentos_fiado = Payment.objects.filter(
            sale__client=self.client,
            method__iexact='fiado'
        )
        
        # Calcular a soma dos valores dos pagamentos fiados
        # Garantir que valores pequenos (como 0.01) sejam contabilizados corretamente
        pagamentos_fiado_total_raw = pagamentos_fiado.aggregate(
            total=Sum('amount')
        )['total']
        
        # Converter para Decimal e garantir que valores pequenos sejam preservados
        if pagamentos_fiado_total_raw is None:
            pagamentos_fiado_total = Decimal('0.00')
        else:
            # Garantir que seja Decimal e quantizado para 2 casas decimais
            pagamentos_fiado_total = Decimal(str(pagamentos_fiado_total_raw)).quantize(Decimal('0.01'))

        # IMPORTANTE: Preservar dívidas iniciais cadastradas manualmente
        # A dívida total = dívida inicial (campo initial_debt) + pagamentos fiados
        from clients.models import Client
        
        # Buscar o cliente atual para obter a dívida inicial
        client_atual = Client.objects.get(pk=self.client.pk)
        divida_inicial = client_atual.initial_debt or Decimal('0.00')
        
        # A dívida final é a soma da dívida inicial + pagamentos fiados
        # Isso garante que dívidas iniciais cadastradas manualmente sejam preservadas
        # IMPORTANTE: Incluir TODOS os centavos, mesmo 0.01
        divida_final = (divida_inicial + pagamentos_fiado_total).quantize(Decimal('0.01'))

        # Atualizar a dívida do cliente
        Client.objects.filter(pk=self.client.pk).update(
            client_debts=divida_final
        )
        # Recarregar o cliente para garantir sincronização
        self.client.refresh_from_db()

    def finalize_and_reserve_stock(self, skip_debt_update=False):
        """
        Finaliza a venda. O estoque já foi reservado quando os itens foram adicionados.
        
        Args:
            skip_debt_update: Se True, não atualiza o cache da dívida do cliente.
                             Mantido para compatibilidade, mas não é mais necessário
                             já que sempre recalculamos do zero sem duplicação.
        """
        if self.status != self.STATUS_OPEN:
            return
        with transaction.atomic():
            sale_locked = Sale.objects.select_for_update().get(pk=self.pk)
            # Verificar se há estoque suficiente (já foi reservado, mas verificar por segurança)
            for item in sale_locked.items.select_related('product'):
                if item.product.quantity < 0:
                    raise ValueError(
                        f'Estoque insuficiente para {item.product.name}. '
                        f'A venda não pode ser finalizada.'
                    )
            # Não subtrair estoque novamente - já foi subtraído quando os itens foram adicionados
            # Apenas mudar o status para finalizada
            sale_locked.status = self.STATUS_FINALIZED
            sale_locked.save(update_fields=['status', 'updated_at'])
            # Sempre recalcular a dívida (não há mais duplicação pois recalculamos do zero)
            if not skip_debt_update:
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
            if self.status == self.STATUS_CANCELLED:
                # Se estava cancelada, o estoque já foi devolvido no cancel()
                # Agora precisamos reservar novamente ao reabrir
                for item in self.items.select_related('product'):
                    if item.product.quantity < item.quantity:
                        raise ValueError(
                            f'Estoque insuficiente para {item.product.name} '
                            f'({item.product.quantity} disponível, {item.quantity} solicitado).'
                        )
                    item.product.quantity -= item.quantity
                    item.product.save(update_fields=['quantity'])
            # Se estava finalizada, o estoque já está reservado, não precisa fazer nada
            # Apenas mudar o status para aberta
            self.status = self.STATUS_OPEN
            self.save(update_fields=['status', 'updated_at'])
            self.update_client_debt_cache()

    def apply_payment(self, amount, method=None, note=None):
        if amount <= 0:
            raise ValueError('Valor do pagamento deve ser positivo.')

        # Verificar se a venda está aberta antes de aplicar o pagamento
        if self.status != self.STATUS_OPEN:
            raise ValueError(
                'Não é possível aplicar pagamento em uma venda que não está aberta.'
            )

        with transaction.atomic():
            sale_locked = Sale.objects.select_for_update().get(pk=self.pk)

            # Verificar novamente o status dentro da transação
            if sale_locked.status != self.STATUS_OPEN:
                raise ValueError('Venda não está mais aberta.')

            # Verificar se ainda há saldo a pagar
            current_balance = sale_locked.balance
            if current_balance <= 0:
                if current_balance < 0:
                    raise ValueError(
                        f'Não é possível realizar pagamento. Há um crédito de R$ {abs(current_balance):.2f} nesta comanda.'
                    )
                raise ValueError('Venda já está totalmente paga.')

            if amount > current_balance:
                raise ValueError(
                    f'O valor informado (R$ {amount:.2f}) é maior que o saldo devido (R$ {current_balance:.2f}).'
                )

            # Obter o modelo Payment antes de usá-lo
            Payment = sale_locked.payments.model

            # Garantir que o amount seja quantizado para 2 casas decimais (incluindo centavos)
            amount_quantized = Decimal(str(amount)).quantize(Decimal('0.01'))

            # Criar o pagamento
            Payment.objects.create(
                sale=sale_locked, amount=amount_quantized, method=method, note=note
            )

            # IMPORTANTE: Recarregar a venda do banco para garantir que o pagamento foi salvo
            sale_locked.refresh_from_db()

            # IMPORTANTE: NÃO adicionar manualmente pagamentos fiados à dívida
            # A dívida será recalculada do zero pelo update_client_debt_cache()
            # Isso garante que não há duplicação

            # Recalcular o valor pago e o saldo após criar o pagamento
            sale_locked.refresh_from_db()
            current_balance = sale_locked.balance

            # Verificar se é pagamento fiado
            is_fiado = method and method.strip().lower() == 'fiado'

            # Só finalizar se o saldo for zero ou negativo (tudo foi pago, incluindo centavos)
            # Não usar tolerância - o saldo deve ser exatamente zero ou negativo
            if current_balance <= Decimal('0.00'):
                # Finalizar a venda
                # Se o último pagamento foi fiado, a dívida já será recalculada no finalize
                # Se não foi fiado, também será recalculada
                sale_locked.finalize_and_reserve_stock(skip_debt_update=False)
            else:
                # Se não finalizou, recalcular a dívida apenas se o pagamento foi fiado
                # Se foi pagamento não-fiado, não precisa recalcular (não afeta a dívida)
                if is_fiado:
                    # Garantir que o cliente está atualizado antes de calcular a dívida
                    if sale_locked.client:
                        sale_locked.client.refresh_from_db()
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
    
    @property
    def subtotal(self):
        """Calcula o subtotal do item (preço × quantidade) com precisão de centavos"""
        subtotal = self.price * self.quantity
        return subtotal.quantize(Decimal('0.01'))

    def save(self, *args, **kwargs):
        with transaction.atomic():
            # Garantir que o preço tenha exatamente 2 casas decimais
            if self.price:
                self.price = self.price.quantize(Decimal('0.01'))
            
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
