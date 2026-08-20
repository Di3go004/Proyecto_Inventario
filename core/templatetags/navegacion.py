from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def url_con(context, **cambios):
    """
    Reconstruye la URL actual cambiando solo los parámetros indicados y
    conservando el resto. Sirve para que al cambiar de página no se pierdan
    los filtros aplicados:

        <a href="?{% url_con pagina=3 %}">3</a>

    Un valor vacío quita el parámetro (útil para "limpiar" uno solo).
    """
    parametros = context['request'].GET.copy()
    for clave, valor in cambios.items():
        if valor in (None, ''):
            parametros.pop(clave, None)
        else:
            parametros[clave] = valor
    return parametros.urlencode()


@register.filter
def get_item(diccionario, clave):
    """Lookup de diccionario por variable, que la plantilla no permite con el punto."""
    if not diccionario:
        return ''
    return diccionario.get(clave, '')
