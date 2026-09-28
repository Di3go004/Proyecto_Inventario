"""
Las salidas nacen abiertas y cada línea se resuelve cuando regresa el técnico.

Antes el regreso de un préstamo se anotaba en la misma salida
(`fecha_devolucion`) y la volvía cero. Eso solo sabía decir "regresó todo", y
reescribía el pasado: el kardex pasaba a decir que el equipo nunca había
salido. Ahora lo que regresa es su propio movimiento, un ingreso de
devolución amarrado a la salida, con su fecha.

Son tres migraciones porque PostgreSQL no deja escribir filas y alterar la
tabla en la misma transacción:

- 0013 (esta): los campos nuevos, con `fecha_devolucion` todavía ahí.
- 0014: convierte los préstamos que había.
- 0015: quita `fecha_devolucion` y pone las restricciones.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0012_unidad_por_movimientos'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='movimientoventa',
            name='cantidad_vendida',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='movimientoventa',
            name='devolucion_de',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='devoluciones', to='ventas.movimientoventa',
            ),
        ),
        migrations.AddField(
            model_name='movimientoventa',
            name='fecha_cierre',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='movimientoventa',
            name='cerrada_por',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='boletas_cerradas', to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='movimientounidad',
            name='vendida',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='movimientoventa',
            name='tipo_transaccion',
            field=models.CharField(
                choices=[
                    ('venta', 'Venta'),
                    ('prestamo_demo', 'Préstamo / Demo'),
                    ('con_tecnico', 'Con el técnico'),
                    ('repuestos', 'Repuestos'),
                    ('materiales_otro', 'Materiales / Otro'),
                    ('devolucion', 'Devolución'),
                    ('ajuste_inicial', 'Ajuste / Saldo inicial'),
                ],
                max_length=20,
            ),
        ),
    ]
