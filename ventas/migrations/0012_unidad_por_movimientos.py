"""
El paradero de una unidad deja de ser dos llaves fijas y pasa a derivarse de
sus movimientos.

Antes la unidad tenía `movimiento_ingreso` y `movimiento_salida`. No
alcanzaba: un equipo que sale a demo y regresa vuelve a salir después, y esa
segunda salida le pisaba la primera. La boleta del demo se quedaba sin sus
seriales — justo lo que no puede pasar con un documento ya firmado.

Los datos que había se conservan: cada llave se convierte en su fila de
MovimientoUnidad antes de borrar las columnas.
"""

import django.db.models.deletion
from django.db import migrations, models


def a_pasos(apps, schema_editor):
    """Las dos llaves de cada unidad se vuelven filas de MovimientoUnidad."""
    Unidad = apps.get_model('ventas', 'UnidadArticulo')
    Paso = apps.get_model('ventas', 'MovimientoUnidad')

    filas = []
    for unidad in Unidad.objects.all().iterator():
        for movimiento_id in (unidad.movimiento_ingreso_id, unidad.movimiento_salida_id):
            if movimiento_id:
                filas.append(Paso(unidad_id=unidad.pk, movimiento_id=movimiento_id))
    Paso.objects.bulk_create(filas, ignore_conflicts=True)


def a_llaves(apps, schema_editor):
    """Vuelta atrás: se reconstruyen las dos llaves desde los pasos."""
    Unidad = apps.get_model('ventas', 'UnidadArticulo')
    Paso = apps.get_model('ventas', 'MovimientoUnidad')

    for unidad in Unidad.objects.all().iterator():
        movimientos = [
            paso.movimiento for paso in
            Paso.objects.filter(unidad_id=unidad.pk)
            .select_related('movimiento').order_by('movimiento__fecha', 'movimiento_id')
        ]
        ingreso = next((m for m in movimientos if m.tipo_documento == 'ingreso'), None)
        salida = next((m for m in reversed(movimientos) if m.tipo_documento == 'salida'), None)
        unidad.movimiento_ingreso_id = ingreso.pk if ingreso else None
        unidad.movimiento_salida_id = salida.pk if salida else None
        unidad.save(update_fields=['movimiento_ingreso', 'movimiento_salida'])


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0011_remove_articulo_numero_serie_articulo_lleva_serie_and_more'),
    ]

    operations = [
        # 1. La tabla nueva, completa, mientras las llaves viejas siguen ahí.
        migrations.CreateModel(
            name='MovimientoUnidad',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ],
            options={
                'verbose_name': 'Unidad del movimiento',
                'verbose_name_plural': 'Unidades del movimiento',
            },
        ),
        migrations.AddField(
            model_name='movimientounidad',
            name='movimiento',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pasos_de_unidad', to='ventas.movimientoventa'),
        ),
        migrations.AddField(
            model_name='movimientounidad',
            name='unidad',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pasos', to='ventas.unidadarticulo'),
        ),

        # 2. Los datos se pasan ANTES de borrar de dónde salen.
        migrations.RunPython(a_pasos, a_llaves),

        # 3. Recién ahora se pueden quitar las llaves viejas.
        migrations.RemoveIndex(
            model_name='unidadarticulo',
            name='ventas_unid_articul_047d89_idx',
        ),
        migrations.RemoveField(
            model_name='unidadarticulo',
            name='movimiento_ingreso',
        ),
        migrations.RemoveField(
            model_name='unidadarticulo',
            name='movimiento_salida',
        ),

        migrations.AddField(
            model_name='unidadarticulo',
            name='movimientos',
            field=models.ManyToManyField(related_name='unidades', through='ventas.MovimientoUnidad', to='ventas.movimientoventa'),
        ),
        migrations.AddIndex(
            model_name='movimientounidad',
            index=models.Index(fields=['unidad', 'movimiento'], name='ventas_movi_unidad__d640a0_idx'),
        ),
        migrations.AddConstraint(
            model_name='movimientounidad',
            constraint=models.UniqueConstraint(fields=('movimiento', 'unidad'), name='unidad_una_vez_por_movimiento'),
        ),
    ]
