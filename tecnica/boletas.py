"""
Hoja de préstamos de Bodega Técnica en PDF (RF-10).

Reproduce FO-SE-066 "Salida - Entrada Insumos Herramienta Bodega Técnica"
(versión 02). A diferencia de las boletas de venta, este formato no es de
un movimiento por hoja: es una hoja de registro donde se van anotando varios
préstamos, uno por fila, con su salida y su entrada en la misma línea. Por eso
se imprime el listado que se esté viendo en pantalla, con sus filtros
aplicados, y no un PDF por préstamo.
"""

import io

from django.utils import timezone
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from core import pdf

from .models import Activo

PAGINA = letter
MARGEN = 12 * mm
ANCHO_UTIL = PAGINA[0] - 2 * MARGEN
FILAS_POR_PAGINA = 12

VERSION = '02'

ENCABEZADOS = [
    'FECHA DE SALIDA', 'FECHA DE ENTRADA', 'CANTIDAD', 'HERRAMIENTA O INSUMO',
    'CÓDIGO INTERNO', 'SOLICITANTE', 'ENTREGADO POR/ DEVUELTO POR', 'RECIBIDO POR',
]
# 'CANTIDAD' necesita 19mm: con menos, el encabezado se partia en 'CANTID/AD'.
ANCHOS = [21 * mm, 21 * mm, 19 * mm, 39 * mm, 22 * mm, 25 * mm, 25 * mm, 20 * mm]
# Filas altas para que las 12 llenen la hoja vertical, como en el talonario.
ALTO_FILA = 14 * mm


def _fecha(valor):
    return timezone.localtime(valor).strftime('%d/%m/%Y') if valor else ''


def _herramienta(prestamo):
    """
    El nombre de la herramienta y, solo si volvió en un estado distinto al que
    salió, una nota debajo. El papel no tiene columna de estado, pero perder
    ese dato justo al imprimir el registro dejaría fuera lo que más cuesta
    rastrear hoy.
    """
    texto = prestamo.activo.nombre_producto
    cambio = (
        prestamo.estado_al_regresar
        and prestamo.estado_al_regresar != prestamo.estado_al_salir
    )
    if cambio:
        etiqueta = dict(Activo.Estado.choices)[prestamo.estado_al_regresar]
        texto += f'<br/><font size="6">Regresó en: {etiqueta}</font>'
    return texto


def _filas(prestamos):
    return [
        [
            Paragraph(_fecha(p.fecha_salida), pdf.CELDA_CENTRADA),
            Paragraph(_fecha(p.fecha_regreso), pdf.CELDA_CENTRADA),
            Paragraph(str(p.cantidad), pdf.CELDA_CENTRADA),
            Paragraph(_herramienta(p), pdf.CELDA),
            Paragraph(p.activo.codigo_interno, pdf.CELDA),
            Paragraph(p.solicitante, pdf.CELDA),
            Paragraph(p.entregado_por or '', pdf.CELDA),
            Paragraph(p.recibido_por or '', pdf.CELDA),
        ]
        for p in prestamos
    ]


def _pagina(prestamos, numero, total, cuantos):
    elementos = [
        pdf.bloque_encabezado(
            'SALIDA - ENTRADA INSUMOS<br/>HERRAMIENTA BODEGA TÉCNICA',
            f'CÓDIGO: FO-SE-066',
            f'VERSIÓN: {VERSION}',
            ANCHO_UTIL,
        ),
        Spacer(1, 2 * mm),
        # El talonario trae el número preimpreso; aquí se deja la línea para
        # anotarlo a mano y se agrega de qué está hecha la hoja.
        Paragraph(
            f'No. ______________ &nbsp;&nbsp;·&nbsp;&nbsp; Página {numero} de {total} '
            f'&nbsp;&nbsp;·&nbsp;&nbsp; {cuantos} préstamo(s) '
            f'&nbsp;&nbsp;·&nbsp;&nbsp; impreso el {timezone.localtime():%d/%m/%Y %H:%M}',
            pdf.CELDA_DERECHA,
        ),
        Spacer(1, 2 * mm),
        pdf.tabla_de_detalle(ENCABEZADOS, _filas(prestamos), ANCHOS, FILAS_POR_PAGINA, ALTO_FILA),
    ]
    return elementos


def hoja_prestamos(prestamos):
    """
    Devuelve los bytes del PDF con los préstamos recibidos. Acepta una lista
    vacía a propósito: imprimir la hoja en blanco para llenarla a mano es un
    uso válido del formato.
    """
    prestamos = list(prestamos)
    cuantos = len(prestamos)

    grupos = [
        prestamos[i:i + FILAS_POR_PAGINA]
        for i in range(0, len(prestamos), FILAS_POR_PAGINA)
    ] or [[]]
    total = len(grupos)

    flujo = []
    for numero, grupo in enumerate(grupos, start=1):
        if numero > 1:
            flujo.append(PageBreak())
        flujo.extend(_pagina(grupo, numero, total, cuantos))

    memoria = io.BytesIO()
    documento = SimpleDocTemplate(
        memoria,
        pagesize=PAGINA,
        leftMargin=MARGEN, rightMargin=MARGEN, topMargin=MARGEN, bottomMargin=MARGEN,
        title='Préstamos de herramienta',
        author=pdf.EMPRESA,
        subject='FO-SE-066',
    )
    documento.build(flujo)
    return memoria.getvalue()
