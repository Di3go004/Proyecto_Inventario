"""
El color del chip de estado de un activo.

Vive acá porque el chip se pinta en cinco plantillas distintas y antes cada
una repetía su propio `if buen_estado / else Mal estado`. Con esa forma,
agregar un estado nuevo obligaba a acordarse de los siete lugares — y el que
se olvidara lo pintaba mal en silencio, porque el `else` se lo tragaba y lo
mostraba como "Mal estado".

Solo devuelve la clase CSS. El texto lo pone Django con
`get_estado_display()`, así que sale del modelo y nunca se desincroniza.
"""

from django import template

from tecnica.models import Activo

register = template.Library()

# De mejor a peor, para que se lean como una escala: verde, ámbar, rojo.
CLASES = {
    Activo.Estado.BUEN_ESTADO: 'chip-good',
    Activo.Estado.PROXIMO_A_REEMPLAZO: 'chip-warn',
    Activo.Estado.MAL_ESTADO: 'chip-critical',
}


@register.filter
def clase_estado(estado):
    """
    'buen_estado' -> 'chip-good'.

    Un estado que no esté en la tabla cae en el chip neutro: se ve raro y se
    nota, que es mejor que teñirlo del color de otro estado.
    """
    return CLASES.get(estado, 'chip-neutral')
