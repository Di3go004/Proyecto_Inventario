"""
Tercera de tres (ver 0013): ya convertidos los préstamos, se quita la columna vieja
y entran las restricciones.

Va aparte porque PostgreSQL no deja alterar una tabla en la misma transacción
en que se acaban de escribir filas con llaves foráneas ("pending trigger
events"). Cada migración es su propia transacción.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0014_salidas_abiertas_datos'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='movimientoventa',
            name='fecha_devolucion',
        ),
        migrations.AddConstraint(
            model_name='movimientoventa',
            constraint=models.CheckConstraint(
                check=models.Q(cantidad_vendida__lte=models.F('cantidad')),
                name='chk_mov_venta_vendidas_hasta_cantidad',
                violation_error_message='No se pueden vender más unidades de las que salieron.',
            ),
        ),
        migrations.AddConstraint(
            model_name='movimientoventa',
            constraint=models.CheckConstraint(
                check=models.Q(devolucion_de__isnull=True) | models.Q(tipo_documento='ingreso'),
                name='chk_mov_venta_devolucion_es_ingreso',
            ),
        ),
    ]
