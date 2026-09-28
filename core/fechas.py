"""
Cómo se escriben las fechas fuera de las plantillas: en los PDF, en los
mensajes de error y en el pie del Excel.

El formato no se define acá: se lee de config/formats/es/formats.py, el mismo
que usan las pantallas. Antes cada PDF y cada mensaje traía su propio
día/mes/año escrito a mano, y cambiar el formato de la empresa obligaba a
buscarlos uno por uno — y el que se escapara seguiría diciendo la fecha al
revés.
"""

from datetime import datetime

from django.utils import formats, timezone


def _en_hora_local(valor):
    """
    Una fecha con hora se muestra en la hora de Guatemala, no en la del
    servidor: guardada en UTC, una salida de las 7 de la noche saldría con
    fecha del día siguiente. Las plantillas lo hacen solas; el código no.
    """
    if isinstance(valor, datetime) and timezone.is_aware(valor):
        return timezone.localtime(valor)
    return valor


def fecha(valor):
    """2026-09-28. Vacío si no hay fecha."""
    if not valor:
        return ''
    return formats.date_format(_en_hora_local(valor), 'DATE_FORMAT')


def fecha_hora(valor):
    """2026-09-28 08:31. Vacío si no hay fecha."""
    if not valor:
        return ''
    return formats.date_format(_en_hora_local(valor), 'DATETIME_FORMAT')
