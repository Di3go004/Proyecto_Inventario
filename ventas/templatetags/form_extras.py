from django import template

register = template.Library()


@register.filter
def get_item(diccionario, clave):
    """Permite {{ mi_diccionario|get_item:variable_clave }} en plantillas
    (Django no soporta lookup dinámico de dict por variable con solo el punto)."""
    if not diccionario:
        return ''
    return diccionario.get(clave, '')
