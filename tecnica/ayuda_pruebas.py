"""
Ayudas para las pruebas de Bodega Técnica.

Desde que la bodega lleva existencia por cantidad, un activo recién creado
tiene existencia 0 y no se puede prestar. Casi toda prueba necesita darle
unidades primero, y hacerlo con un ingreso —en vez de escribir el campo a
mano— es importante: así se prueba contra el mismo camino que usa el sistema
de verdad, y no contra un estado que en producción no podría existir.
"""

from tecnica.models import MovimientoActivo


def dar_existencia(activo, cantidad, usuario, **extra):
    """Registra un ingreso y deja el activo con esa existencia."""
    MovimientoActivo.objects.create(
        tipo=MovimientoActivo.Tipo.INGRESO,
        activo=activo, cantidad=cantidad, usuario=usuario, **extra,
    )
    activo.refresh_from_db()
    return activo


def dar_de_baja(activo, cantidad, usuario, motivo=MovimientoActivo.Motivo.DANADO, **extra):
    """Descarta unidades: es lo único que baja la existencia."""
    MovimientoActivo.objects.create(
        tipo=MovimientoActivo.Tipo.BAJA,
        activo=activo, cantidad=cantidad, usuario=usuario, motivo=motivo, **extra,
    )
    activo.refresh_from_db()
    return activo
