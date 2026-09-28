"""
Formatos de número y fecha para Guatemala.

Django trae formatos para "es" genérico (España), que usa la coma como
separador decimal: los precios salían como `Q 1.500,00`. En Guatemala es al
revés — punto para los decimales y coma para los miles: `Q 1,500.00`.

Django no incluye un locale es-GT, así que se sobreescriben solo los valores
que cambian mediante FORMAT_MODULE_PATH (ver config/settings.py). Todo lo que
no esté acá lo sigue tomando del "es" de Django.
"""

DECIMAL_SEPARATOR = '.'
THOUSAND_SEPARATOR = ','
NUMBER_GROUPING = 3

# El estándar de la empresa es año-mes-día: la ISO 8601 (2026-09-28). Es el
# único lugar donde se define. Las pantallas lo toman con |date:"DATE_FORMAT"
# y los PDF, los mensajes y el Excel con core/fechas.py, así que cambiarlo acá
# lo cambia en todo el sistema.
#
# Entre la fecha y la hora va un espacio y no la "T" de la norma: la ISO lo
# permite por acuerdo, y "2026-09-28 08:31" se lee mejor en una boleta que
# "2026-09-28T08:31".
DATE_FORMAT = 'Y-m-d'
DATETIME_FORMAT = 'Y-m-d H:i'
SHORT_DATE_FORMAT = 'Y-m-d'
SHORT_DATETIME_FORMAT = 'Y-m-d H:i'

# Cómo se acepta una fecha escrita a mano en un formulario. Se sigue aceptando
# día/mes/año por si alguien la escribe como antes: no hay forma de
# confundirlas, porque nunca se acepta mes/día.
DATE_INPUT_FORMATS = ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']
DATETIME_INPUT_FORMATS = [
    '%Y-%m-%dT%H:%M',      # el que manda <input type="datetime-local">
    '%Y-%m-%d %H:%M:%S',
    '%Y-%m-%d %H:%M',
    '%d/%m/%Y %H:%M',
]
