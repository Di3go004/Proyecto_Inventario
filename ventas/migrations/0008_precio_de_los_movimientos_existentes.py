"""
Rellena el precio de los movimientos que ya existían.

El campo nace en 0, y con 0 la boleta impresa diría "Q 0.00" en movimientos
que sí tuvieron un precio. Como antes de este cambio el único precio que
existía era el del catálogo, es el mejor dato disponible para esas filas: es
exactamente lo que la boleta habría impreso hasta ahora.

De aquí en adelante cada movimiento guarda el suyo.
"""

from django.db import migrations


def copiar_precio_del_catalogo(apps, schema_editor):
    Movimiento = apps.get_model('ventas', 'MovimientoVenta')
    for movimiento in Movimiento.objects.select_related('articulo').iterator():
        producto = movimiento.articulo
        if producto and not movimiento.precio_unitario:
            movimiento.precio_unitario = producto.precio
            movimiento.save(update_fields=['precio_unitario'])


def no_se_deshace(apps, schema_editor):
    """El campo se borra con la migración de esquema; no hay nada que revertir."""


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0007_movimientoventa_precio_unitario'),
    ]

    operations = [
        migrations.RunPython(copiar_precio_del_catalogo, no_se_deshace),
    ]
