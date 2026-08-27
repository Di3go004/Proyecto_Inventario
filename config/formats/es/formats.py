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

# Las boletas y los formatos en papel de la empresa usan día/mes/año.
DATE_FORMAT = 'd/m/Y'
DATETIME_FORMAT = 'd/m/Y H:i'
SHORT_DATE_FORMAT = 'd/m/Y'
SHORT_DATETIME_FORMAT = 'd/m/Y H:i'

# Cómo se acepta una fecha escrita a mano en un formulario.
DATE_INPUT_FORMATS = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y']
DATETIME_INPUT_FORMATS = [
    '%Y-%m-%dT%H:%M',      # el que manda <input type="datetime-local">
    '%d/%m/%Y %H:%M',
    '%Y-%m-%d %H:%M:%S',
    '%Y-%m-%d %H:%M',
]
