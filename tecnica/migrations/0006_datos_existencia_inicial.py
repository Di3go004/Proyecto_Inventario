"""
Pasa los activos que ya existían al modelo de existencia por cantidad.

Antes cada registro era una unidad física, así que a todos les corresponde
existencia 1. Los que estaban marcados "De baja" quedan en 0: ese estado
desaparece —ahora dar de baja es un movimiento con cantidad— pero el dato de
que se descartaron no se puede perder, así que se convierte en una baja de
verdad, con fecha y todo.

En una base recién instalada no hay activos y esta migración no hace nada.
"""

from django.db import migrations

ESTADO_VIEJO_DE_BAJA = 'de_baja'
MAL_ESTADO = 'mal_estado'


def _autor(apps):
    """
    Los movimientos necesitan un usuario (el campo es obligatorio y protegido).
    Se usa el primer administrador que haya: es un asiento de arrastre, no
    algo que alguien hizo de verdad, y así al menos queda atribuido a una
    cuenta real en vez de inventar una.
    """
    Usuario = apps.get_model('usuarios', 'Usuario')
    return (
        Usuario.objects.filter(is_superuser=True).order_by('id').first()
        or Usuario.objects.filter(rol='administrador').order_by('id').first()
        or Usuario.objects.order_by('id').first()
    )


def sembrar_existencia(apps, schema_editor):
    Activo = apps.get_model('tecnica', 'Activo')
    MovimientoActivo = apps.get_model('tecnica', 'MovimientoActivo')
    PrestamoActivo = apps.get_model('tecnica', 'PrestamoActivo')

    if not Activo.objects.exists():
        return

    usuario = _autor(apps)
    if usuario is None:
        raise RuntimeError(
            'Hay activos pero ningún usuario al que atribuirles el saldo inicial. '
            'Creá el usuario administrador y volvé a correr migrate.'
        )

    for activo in Activo.objects.all():
        de_baja = activo.estado == ESTADO_VIEJO_DE_BAJA

        MovimientoActivo.objects.create(
            tipo='ajuste', activo=activo, cantidad=1, usuario=usuario,
            fecha=activo.fecha_creacion,
            observacion='Saldo inicial al pasar Bodega Técnica a existencia por cantidad.',
        )
        if de_baja:
            MovimientoActivo.objects.create(
                tipo='baja', activo=activo, cantidad=1, usuario=usuario,
                fecha=activo.fecha_actualizacion, motivo='danado',
                observacion='Estaba marcado "De baja" antes de llevar existencia por cantidad.',
            )

        activo.existencia = 0 if de_baja else 1
        # El estado ya solo describe la condición; "De baja" dejó de ser uno.
        if de_baja:
            activo.estado = MAL_ESTADO
        activo.save(update_fields=['existencia', 'estado'])

    PrestamoActivo.objects.filter(estado_al_regresar=ESTADO_VIEJO_DE_BAJA).update(
        estado_al_regresar=MAL_ESTADO,
    )


def revertir(apps, schema_editor):
    """
    Al revertir se borran los asientos de arrastre que creó esta migración.
    No se intenta reconstruir el estado "De baja": esa columna vuelve a
    aceptarlo por la migración de esquema, pero cuál activo lo tenía ya no se
    puede saber sin adivinar, y adivinar sería peor que dejarlo en mal estado.
    """
    MovimientoActivo = apps.get_model('tecnica', 'MovimientoActivo')
    MovimientoActivo.objects.filter(
        observacion__startswith='Saldo inicial al pasar Bodega Técnica',
    ).delete()
    MovimientoActivo.objects.filter(
        observacion__startswith='Estaba marcado "De baja"',
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tecnica', '0005_existencia_por_cantidad'),
        ('usuarios', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(sembrar_existencia, revertir),
    ]
