# Generated by Django 5.2 on 2025-04-22 13:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('canchas', '0013_egreso_metodo_pago'),
    ]

    operations = [
        migrations.AddField(
            model_name='venta',
            name='metodo_pago',
            field=models.CharField(choices=[('efectivo', 'Efectivo'), ('tarjeta_debito', 'Tarjeta de Débito'), ('tarjeta_credito', 'Tarjeta de Crédito'), ('transferencia', 'Transferencia'), ('mercado_pago', 'Mercado Pago'), ('otro', 'Otro')], default='efectivo', max_length=20, verbose_name='Método de Pago'),
        ),
    ]
