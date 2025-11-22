# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0002_alter_client_photo'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='initial_debt',
            field=models.DecimalField(
                decimal_places=2,
                default=0.0,
                help_text='Dívida cadastrada manualmente ao criar o cliente (não vem de pagamentos fiados)',
                max_digits=10,
                verbose_name='Dívida Inicial',
            ),
        ),
    ]

