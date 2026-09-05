"""
El color y el texto del chip de nivel de reposición (RF-11).

Vive en core porque ahora lo usan las dos bodegas: `Articulo.nivel_alerta` y
`Activo.nivel_alerta` devuelven lo mismo y se pintan igual.

Antes cada plantilla repetía su propio `if critico / elif alerta / elif
optimo / else normal` — cuatro veces, y Bodega Técnica habría sumado dos más.
Con esa forma, cambiar un color o agregar un nivel obliga a acordarse de
todas, y la que se olvide lo pinta mal en silencio.
"""

from django import template

register = template.Library()

# De peor a mejor. 'normal' va neutro a propósito: es "no pasa nada", y no
# debe competir visualmente con lo que sí necesita atención.
NIVELES = {
    'critico': ('chip-critical', 'Crítico'),
    'alerta': ('chip-warn', 'Alerta'),
    'normal': ('chip-neutral', 'Normal'),
    'optimo': ('chip-good', 'Óptimo'),
}


@register.filter
def clase_nivel(nivel):
    """'critico' -> 'chip-critical'."""
    return NIVELES.get(nivel, ('chip-neutral', ''))[0]


@register.filter
def texto_nivel(nivel):
    """'critico' -> 'Crítico'."""
    return NIVELES.get(nivel, ('', nivel))[1]
