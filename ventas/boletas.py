"""
Boletas de Bodega 1 y 2 en PDF (RF-10).

Reproducen los dos formatos de papel que hoy se llenan a mano:
  - FO-SE-013 "Ingreso a Bodega"  (versión 03)
  - FO-SE-012 "Salida de Bodega"  (versión 03)

Un folio puede llevar más líneas de las que caben en una hoja, así que el
detalle se parte en varias páginas y cada una repite el encabezado completo
con su "Página X de Y" — igual que cuando en bodega usan dos hojas del
talonario para un mismo movimiento.
"""

import io

from django.utils import timezone
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
)

from core import pdf

from .models import MovimientoVenta

PAGINA = landscape(letter)
MARGEN = 10 * mm
ANCHO_UTIL = PAGINA[0] - 2 * MARGEN
# 7 filas: con más, una hoja llena de descripciones de dos renglones empujaba
# el bloque de firmas a una segunda página casi vacía. Con 7 la boleta cabe
# entera aunque todas las líneas ocupen el máximo.
FILAS_POR_PAGINA = 7
# Filas con algo de aire: sobre la boleta impresa a veces corrigen a mano.
ALTO_FILA = 9 * mm

VERSION = '03'

# Las mismas cuatro casillas que trae impreso el talonario.
OPCIONES_TIPO = [
    (MovimientoVenta.TipoTransaccion.VENTA, 'Equipo venta'),
    (MovimientoVenta.TipoTransaccion.PRESTAMO_DEMO, 'Equipo préstamo'),
    (MovimientoVenta.TipoTransaccion.REPUESTOS, 'Repuestos'),
    (MovimientoVenta.TipoTransaccion.MATERIALES_OTRO, 'Materiales / Otro'),
]

COLUMNAS_INGRESO = (
    ['Cant.', 'Descripción', 'Precio', 'Nombre de proveedor', 'No. Factura'],
    [18 * mm, 107 * mm, 30 * mm, 55 * mm, 45 * mm],
)
COLUMNAS_SALIDA = (
    ['CANTIDAD', 'DESCRIPCIÓN Y CÓDIGO', 'NOMBRE CLIENTE'],
    [22 * mm, 153 * mm, 80 * mm],
)


# Un nombre más largo que esto haría que la fila creciera a tres renglones y,
# con la hoja llena, empujaría el bloque de firmas a una segunda página casi
# vacía. El nombre completo siempre queda en el sistema; la boleta es el
# resumen que se imprime.
MAX_DESCRIPCION = 95


def _descripcion(linea):
    """Producto + código interno, como se escribe en la columna del papel."""
    articulo = linea.articulo
    detalle = ' '.join(p for p in (articulo.marca, articulo.modelo, articulo.capacidad) if p)
    texto = articulo.nombre_producto
    if detalle:
        texto += f' · {detalle}'
    if len(texto) > MAX_DESCRIPCION:
        texto = texto[:MAX_DESCRIPCION - 1].rstrip() + '…'
    return f'{texto}<br/><font size="7">{articulo.codigo_interno}</font>'


def _filas(lineas, es_ingreso):
    if es_ingreso:
        return [
            [
                Paragraph(str(linea.cantidad), pdf.CELDA_CENTRADA),
                Paragraph(_descripcion(linea), pdf.CELDA),
                Paragraph(f'Q {linea.articulo.precio:,.2f}', pdf.CELDA_DERECHA),
                Paragraph(str(linea.proveedor or ''), pdf.CELDA),
                Paragraph(linea.no_factura or '', pdf.CELDA),
            ]
            for linea in lineas
        ]
    return [
        [
            Paragraph(str(linea.cantidad), pdf.CELDA_CENTRADA),
            Paragraph(_descripcion(linea), pdf.CELDA),
            Paragraph(linea.cliente_nombre or '', pdf.CELDA),
        ]
        for linea in lineas
    ]


def _datos_y_casillas(cabecera, es_ingreso):
    """El folio y los campos de arriba, con el bloque de casillas a la derecha."""
    fecha = timezone.localtime(cabecera.fecha).strftime('%d/%m/%Y')

    izquierda = [
        Paragraph(f'No. {cabecera.folio}', pdf.FOLIO),
        Spacer(1, 3 * mm),
        pdf.campo('FECHA:', fecha),
        pdf.campo('SOLICITADO POR:', cabecera.solicitado_por),
    ]
    if not es_ingreso:
        izquierda.append(pdf.campo('ENTREGADO POR:', cabecera.entregado_por))

    ancho_casillas = 40 * mm
    return pdf.sin_bordes(Table(
        [[izquierda, pdf.casillas(OPCIONES_TIPO, cabecera.tipo_transaccion)]],
        colWidths=[ANCHO_UTIL - ancho_casillas, ancho_casillas],
    ))


def _pie_de_salida(cabecera):
    """
    Solo FO-SE-012 lo trae: los datos de factura/envío/devolución y los tres
    espacios de firma. En la hoja apaisada las firmas caben una al lado de la
    otra, que aprovecha mejor el ancho que apilarlas como en el talonario.
    """
    campos = pdf.sin_bordes(Table(
        [[
            pdf.campo('No. FACTURA', cabecera.no_factura, ancho_linea=45 * mm, alto=6 * mm),
            pdf.campo('ENVÍO Y/O RECIBO', cabecera.envio_recibo, ancho_linea=45 * mm, alto=6 * mm),
            pdf.campo('DEVUELTO POR:', cabecera.devuelto_por, ancho_linea=45 * mm, alto=6 * mm),
        ]],
        colWidths=[ANCHO_UTIL / 3] * 3,
    ))

    ancho_firma = ANCHO_UTIL / 3 - 8 * mm
    firmas = pdf.sin_bordes(Table(
        [[
            pdf.linea_de_firma('NOMBRE Y FIRMA AUT.', ancho_firma),
            pdf.linea_de_firma('NOMBRE Y FIRMA REC.', ancho_firma),
            pdf.linea_de_firma('NOMBRE Y FIRMA DEV.', ancho_firma),
        ]],
        colWidths=[ANCHO_UTIL / 3] * 3,
    ))

    return [Spacer(1, 3 * mm), campos, Spacer(1, 5 * mm), KeepTogether(firmas)]


def _pagina(cabecera, lineas, es_ingreso, numero, total):
    titulo = 'INGRESO A BODEGA' if es_ingreso else 'SALIDA DE BODEGA'
    codigo = 'FO-SE-013' if es_ingreso else 'FO-SE-012'
    encabezados, anchos = COLUMNAS_INGRESO if es_ingreso else COLUMNAS_SALIDA

    elementos = [
        pdf.bloque_encabezado(
            titulo,
            f'Código: {codigo}<br/>Versión: {VERSION}',
            f'Página {numero} de {total}',
            ANCHO_UTIL,
        ),
        Spacer(1, 4 * mm),
        _datos_y_casillas(cabecera, es_ingreso),
        Spacer(1, 4 * mm),
        pdf.tabla_de_detalle(encabezados, _filas(lineas, es_ingreso), anchos, FILAS_POR_PAGINA, ALTO_FILA),
    ]

    # La observación no viene impresa en el talonario, pero si el operador
    # escribió una hay que llevarla a la boleta o se pierde al imprimir.
    if cabecera.observacion and numero == total:
        elementos += [
            Spacer(1, 3 * mm),
            Paragraph(f'<b>OBSERVACIÓN:</b> {cabecera.observacion}', pdf.CELDA),
        ]

    if not es_ingreso and numero == total:
        elementos += _pie_de_salida(cabecera)

    return elementos


def agrupar_en_paginas(lineas):
    """Reparte las líneas del documento en hojas de FILAS_POR_PAGINA."""
    return [lineas[i:i + FILAS_POR_PAGINA] for i in range(0, len(lineas), FILAS_POR_PAGINA)]


def boleta_documento(folio):
    """
    Devuelve los bytes del PDF de un documento completo (todas las líneas que
    comparten el folio). Lanza MovimientoVenta.DoesNotExist si el folio no
    existe, para que la vista responda 404 en vez de un PDF vacío.
    """
    lineas = list(
        MovimientoVenta.objects
        .filter(folio=folio)
        .select_related('articulo', 'proveedor')
        .order_by('id')
    )
    if not lineas:
        raise MovimientoVenta.DoesNotExist(f'No hay ningún documento con folio {folio}.')

    cabecera = lineas[0]
    es_ingreso = cabecera.tipo_documento == MovimientoVenta.TipoDocumento.INGRESO

    grupos = agrupar_en_paginas(lineas)
    total = len(grupos)

    flujo = []
    for numero, grupo in enumerate(grupos, start=1):
        if numero > 1:
            flujo.append(PageBreak())
        flujo.extend(_pagina(cabecera, grupo, es_ingreso, numero, total))

    memoria = io.BytesIO()
    documento = SimpleDocTemplate(
        memoria,
        pagesize=PAGINA,
        leftMargin=MARGEN, rightMargin=MARGEN, topMargin=MARGEN, bottomMargin=MARGEN,
        title=f'{"Ingreso" if es_ingreso else "Salida"} {folio}',
        author=pdf.EMPRESA,
        subject='FO-SE-013' if es_ingreso else 'FO-SE-012',
    )
    documento.build(flujo)
    return memoria.getvalue()
