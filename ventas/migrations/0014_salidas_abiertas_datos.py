"""
Segunda de tres: convierte los préstamos que había al modelo de salidas
abiertas. Ver 0013 para el porqué del cambio.

Los datos se convierten sin mover la existencia de nada:

- Un préstamo que ya regresó: su regreso se vuelve una devolución con la fecha
  y el "devuelto por" que tenía, y sus seriales pasan a esa devolución.
- Un préstamo que sigue afuera: queda pendiente, como estaba.
- Una venta, repuestos o materiales: salieron para no volver, así que quedan
  vendidos.
- La boleta a la que ya no le falta nada queda cerrada, con la fecha de su
  último movimiento.

Hacia atrás solo se puede volver aproximado: el modelo viejo no sabía de
regresos parciales, así que una línea que regresó por partes vuelve como
regresada entera en la fecha de su último regreso.

Va sola, sin cambios de estructura: PostgreSQL no deja alterar una tabla en la
misma transacción en que se escribieron filas con llaves foráneas ("pending
trigger events"), y cada migración es su propia transacción.
"""

from django.db import migrations


def a_salidas_abiertas(apps, schema_editor):
    Movimiento = apps.get_model('ventas', 'MovimientoVenta')
    Paso = apps.get_model('ventas', 'MovimientoUnidad')

    for salida in Movimiento.objects.filter(tipo_documento='salida').order_by('fecha', 'id'):
        if salida.tipo_transaccion == 'prestamo_demo':
            if salida.fecha_devolucion:
                devolucion = Movimiento.objects.create(
                    folio=salida.folio,
                    tipo_documento='ingreso',
                    tipo_transaccion='devolucion',
                    articulo_id=salida.articulo_id,
                    cantidad=salida.cantidad,
                    fecha=salida.fecha_devolucion,
                    usuario_id=salida.usuario_id,
                    precio_unitario=salida.precio_unitario,
                    cliente_nombre=salida.cliente_nombre,
                    devolucion_de_id=salida.pk,
                    devuelto_por=salida.devuelto_por,
                )
                Paso.objects.bulk_create([
                    Paso(movimiento_id=devolucion.pk, unidad_id=paso.unidad_id)
                    for paso in Paso.objects.filter(movimiento_id=salida.pk)
                ])
            # El que sigue afuera queda pendiente: no hay nada que anotar.
        else:
            salida.cantidad_vendida = salida.cantidad
            Paso.objects.filter(movimiento_id=salida.pk).update(vendida=True)

        # El "devuelto por" ahora vive en la devolución.
        salida.devuelto_por = ''
        salida.save(update_fields=['cantidad_vendida', 'devuelto_por'])

    # Cerrar lo que ya no tiene nada pendiente. Por boleta, porque se cierra
    # entera; una salida sin número se trata sola.
    salidas = list(Movimiento.objects.filter(tipo_documento='salida'))
    boletas = {}
    for salida in salidas:
        clave = salida.folio or f'sin-folio-{salida.pk}'
        boletas.setdefault(clave, []).append(salida)

    for lineas in boletas.values():
        fechas, resueltas = [], True
        for linea in lineas:
            devoluciones = list(Movimiento.objects.filter(devolucion_de_id=linea.pk))
            devueltas = sum(d.cantidad for d in devoluciones)
            if linea.cantidad - linea.cantidad_vendida - devueltas > 0:
                resueltas = False
                break
            fechas.append(linea.fecha)
            fechas += [d.fecha for d in devoluciones]
        if not resueltas:
            continue
        ultima = max(lineas, key=lambda linea: (linea.fecha, linea.pk))
        Movimiento.objects.filter(pk__in=[linea.pk for linea in lineas]).update(
            fecha_cierre=max(fechas), cerrada_por_id=ultima.usuario_id,
        )


def a_prestamos(apps, schema_editor):
    Movimiento = apps.get_model('ventas', 'MovimientoVenta')
    Paso = apps.get_model('ventas', 'MovimientoUnidad')

    for devolucion in Movimiento.objects.filter(devolucion_de__isnull=False).order_by('fecha', 'id'):
        Movimiento.objects.filter(pk=devolucion.devolucion_de_id).update(
            tipo_transaccion='prestamo_demo',
            fecha_devolucion=devolucion.fecha,
            devuelto_por=devolucion.devuelto_por,
        )
    Paso.objects.filter(movimiento__devolucion_de__isnull=False).delete()
    Movimiento.objects.filter(devolucion_de__isnull=False).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0013_salidas_abiertas'),
    ]

    operations = [
        migrations.RunPython(a_salidas_abiertas, a_prestamos),
    ]
