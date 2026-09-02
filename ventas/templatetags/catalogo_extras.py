"""
Formato de los datos del catálogo en las plantillas.
"""

from django import template

from ventas.models import SIN_SERIAL

register = template.Library()


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
