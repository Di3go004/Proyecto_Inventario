"""
Enlace a un archivo estático que cambia de URL cuando el archivo cambia.

En desarrollo, Django sirve los estáticos sin cabeceras de caché. Los
navegadores entonces aplican caché heurística: se quedan con la copia que ya
tienen y no vuelven a preguntar. El efecto práctico es que al cambiar el CSS
se sigue viendo el diseño viejo hasta forzar una recarga completa — y como el
archivo sí cambió en el servidor, es muy fácil creer que el cambio no se
aplicó y salir a buscar el error donde no está.

Agregando la fecha de modificación del archivo a la URL, cada cambio produce
una dirección distinta y el navegador la pide de nuevo sola.

En producción no hace falta: WhiteNoise ya sirve los estáticos con un hash en
el nombre (app.ced5dc6d.css), así que ahí se devuelve la URL tal cual.
"""

import os

from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static as url_estatica

register = template.Library()


@register.simple_tag
def estatico(ruta):
    url = url_estatica(ruta)

    if not settings.DEBUG:
        return url

    archivo = finders.find(ruta)
    if not archivo:
        # El archivo no existe: se devuelve la URL igual para que el 404 se
        # vea en el navegador, en vez de reventar al renderizar la página.
        return url

    return f'{url}?v={int(os.path.getmtime(archivo))}'
