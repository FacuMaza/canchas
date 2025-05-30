# Generated by Django 5.2 on 2025-04-10 19:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('canchas', '0006_reserva_precio_reserva_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Extra',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(help_text='Ej: Bebida Isotónica, Alquiler Paleta, Tubo Pelotas', max_length=100, unique=True, verbose_name='Nombre del Extra')),
                ('descripcion', models.TextField(blank=True, null=True, verbose_name='Descripción')),
                ('precio_actual', models.DecimalField(decimal_places=2, help_text='El precio de venta actual de este extra.', max_digits=10, verbose_name='Precio Actual')),
                ('activo', models.BooleanField(default=True, help_text='Indica si este extra está disponible para la venta.', verbose_name='Activo')),
            ],
            options={
                'verbose_name': 'Extra',
                'verbose_name_plural': 'Extras',
                'ordering': ['nombre'],
            },
        ),
    ]
