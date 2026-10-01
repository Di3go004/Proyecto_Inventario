"""
Formato de los datos del catálogo en las plantillas.
"""

from django import template

from ventas.models import SIN_SERIAL, UnidadArticulo

register = template.Library()

PARADERO = UnidadArticulo.Paradero

# Verde lo que está en bodega, ámbar lo que salió y todavía puede volver, gris
# lo que ya no vuelve. Es lo que se lee de un vistazo al buscar la plataforma
# de un indicador: si está, si puede regresar o si ya no.
CLASES_DE_PARADERO = {
    PARADERO.EN_BODEGA: 'chip-good',
    PARADERO.CON_TECNICO: 'chip-warn',
    PARADERO.DEMO: 'chip-warn',
    PARADERO.PENDIENTE: 'chip-warn',
    PARADERO.VENDIDA: 'chip-neutral',
    PARADERO.SIN_MOVIMIENTOS: 'chip-neutral',
}


@register.filter
def serial(numero_serie):
    """
    Escribe el número de serie, o "S/S" si no tiene.

    Existe para las pantallas que trabajan con datos sueltos y no con un
    Articulo —la vista previa de la carga masiva, que muestra filas del Excel
    todavía sin guardar—. Donde sí hay un Articulo se usa su propiedad
    `serial`; las dos leen la misma constante para que no se desfasen.
    """
    return numero_serie or SIN_SERIAL


@register.filter
def clase_paradero(paradero):
    """'en_bodega' -> 'chip-good'. El texto lo da el propio paradero (.label)."""
    return CLASES_DE_PARADERO.get(paradero, 'chip-neutral')
