"""
Un resultado más para las líneas de salida: usado.

Lo que se gasta en el trabajo —un desengrasante, por ejemplo— no se vendió,
porque nadie lo pagó, pero tampoco regresa. Solo había dos resultados, vendido
y devuelto, así que se marcaba vendido (inflando las ventas) o se quedaba
pendiente para siempre (y la boleta nunca se podía cerrar).

La restricción de la base pasa de "no se venden más de las que salieron" a
"entre vendidas y usadas no pasan de las que salieron". Las líneas que ya
existen arrancan con 0 usadas, así que ninguna cambia.
"""

import django.db.models.expressions
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_proveedor_origen'),
        ('ventas', '0015_salidas_abiertas_limpieza'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='movimientoventa',
            name='chk_mov_venta_vendidas_hasta_cantidad',
        ),
        migrations.AddField(
            model_name='movimientoventa',
            name='cantidad_usada',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddConstraint(
            model_name='movimientoventa',
            constraint=models.CheckConstraint(
                check=models.Q((
                    'cantidad__gte',
                    django.db.models.expressions.CombinedExpression(
                        models.F('cantidad_vendida'), '+', models.F('cantidad_usada'),
                    ),
                )),
                name='chk_mov_venta_resultado_hasta_cantidad',
                violation_error_message='Entre vendidas y usadas no pueden ser más de las que salieron.',
            ),
        ),
    ]
