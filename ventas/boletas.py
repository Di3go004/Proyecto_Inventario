"""
Boletas de Bodega 1 y 2 en PDF (RF-10).

Reproducen los dos formatos de papel que hoy se llenan a mano:
  - FO-SE-013 "Ingreso a Bodega"  (versión 03)
  - FO-SE-012 "Salida de Bodega"  (versión 03)

**Van en media carta**, que es el tamaño real del talonario de la empresa
(ver las fotos en pdf/). Media carta es la hoja carta partida a la mitad:
216 × 140 mm, apaisada. Ojo con el HALF_LETTER de ReportLab — ese mide
140 × 203 mm (5.5 × 8"), que es otro tamaño y no calza con el talonario.

Que el tamaño coincida no es un detalle estético: estas boletas se imprimen,
se firman y se archivan junto a las de papel de los años anteriores. Si
salieran en carta completa no entrarían en el mismo folder.

El formato de Bodega Técnica (FO-SE-066) sí es carta completa y vive en
tecnica/boletas.py.
"""

import io

from django.utils import timezone
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
)

from core import pdf

from . import documentos
from .models import MovimientoVenta

# Media carta apaisada: la hoja carta cortada a la mitad por el lado largo.
MEDIA_CARTA = (letter[0], letter[1] / 2)      # 216 × 140 mm

PAGINA = MEDIA_CARTA
MARGEN = 7 * mm
ANCHO_UTIL = PAGINA[0] - 2 * MARGEN           # ≈ 202 mm

# El talonario real trae 9 renglones y llena la hoja. Antes eran 6 y bastante
# más altos, y quedaba un tercio de la media carta en blanco: impresa al lado
# de una boleta de papel se veía como una ampliación de la misma boleta.
FILAS_POR_PAGINA = 9

# El ingreso puede estirar más el renglón porque no lleva el bloque de firmas
# abajo; la salida sí, y ahí el espacio se reparte.
#
# Son los valores más altos con los que las 9 filas todavía caben en una sola
# hoja **con observación**, que es el caso más largo: la observación no viene
# en el talonario de papel, se agregó para no perder lo que escribió el
# operador, y ocupa un renglón extra al pie.
#
# Hay pruebas que lo comprueban armando el PDF y contando hojas, porque
# calcularlo a mano se queda corto: el relleno de las celdas y el de la fila
# de encabezado se derivan de este mismo alto.
ALTO_FILA_INGRESO = 8.6 * mm
ALTO_FILA_SALIDA = 6.1 * mm

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
    [13 * mm, 84 * mm, 22 * mm, 45 * mm, 38 * mm],
)
COLUMNAS_SALIDA = (
    ['CANTIDAD', 'DESCRIPCIÓN Y CÓDIGO', 'NOMBRE CLIENTE'],
    [20 * mm, 122 * mm, 60 * mm],
)

# Lo que ocupa el relleno lateral de una celda de tabla en ReportLab.
RELLENO_CELDA = 12

# En el papel la línea para llenar a mano llega casi hasta las casillas.
ANCHO_LINEA_DATO = 90 * mm

# Alto de cada renglón del pie de la salida (factura, envío, firmas).
ALTO_PIE = 6.4 * mm


def _recortar(texto, ancho_columna, estilo):
    """
    Recorta el texto para que entre en UN renglón de esa columna.

    Se mide con las métricas reales de la fuente en vez de contar caracteres:
    contando, una "W" y una "l" valen lo mismo y el cálculo falla justo con
    los nombres largos, que es cuando importa. Y si una fila creciera a dos
    renglones, en media carta el bloque de firmas se iría a otra hoja.
    """
    disponible = ancho_columna - RELLENO_CELDA
    if stringWidth(texto, estilo.fontName, estilo.fontSize) <= disponible:
        return texto

    while texto and stringWidth(texto + '…', estilo.fontName, estilo.fontSize) > disponible:
        texto = texto[:-1]
    return texto.rstrip() + '…'


def _descripcion(linea, ancho_columna):
    """
    Producto, marca/modelo y código en un solo renglón — la columna del papel
    se llama justamente "DESCRIPCIÓN Y CÓDIGO".
    """
    producto = linea.producto
    # capacidad solo la tienen los artículos de venta; la herramienta no.
    detalle = ' '.join(
        p for p in (producto.marca, producto.modelo, getattr(producto, 'capacidad', '')) if p
    )
    partes = [producto.nombre_producto]
    if detalle:
        partes.append(detalle)
    partes.append(producto.codigo_interno)
    return _recortar(' · '.join(partes), ancho_columna, pdf.CELDA_CHICA)


def _filas(lineas, es_ingreso):
    _encabezados, anchos = COLUMNAS_INGRESO if es_ingreso else COLUMNAS_SALIDA
    ancho_descripcion = anchos[1]

    if es_ingreso:
        return [
            [
                Paragraph(str(linea.cantidad), pdf.CELDA_CHICA_CENTRADA),
                Paragraph(_descripcion(linea, ancho_descripcion), pdf.CELDA_CHICA),
                Paragraph(f'Q {linea.producto.precio:,.2f}', pdf.CELDA_CHICA_DERECHA),
                # El proveedor sale del artículo: ya está en el catálogo, así
                # que pedirlo otra vez al registrar el ingreso era escribir
                # dos veces el mismo dato. Si el movimiento trae uno propio
                # (compra puntual a otro proveedor), ese manda.
                Paragraph(_recortar(str(linea.proveedor_efectivo or ''),
                                    anchos[3], pdf.CELDA_CHICA), pdf.CELDA_CHICA),
                Paragraph(linea.no_factura or '', pdf.CELDA_CHICA),
            ]
            for linea in lineas
        ]
    return [
        [
            Paragraph(str(linea.cantidad), pdf.CELDA_CHICA_CENTRADA),
            Paragraph(_descripcion(linea, ancho_descripcion), pdf.CELDA_CHICA),
            Paragraph(_recortar(linea.cliente_nombre or '', anchos[2], pdf.CELDA_CHICA), pdf.CELDA_CHICA),
        ]
        for linea in lineas
    ]


def _datos_y_casillas(cabecera, es_ingreso):
    """El folio y los campos de arriba, con el bloque de casillas a la derecha."""
    fecha = timezone.localtime(cabecera.fecha).strftime('%d/%m/%Y')

    izquierda = [
        Paragraph(f'No. {cabecera.folio}', pdf.FOLIO_CHICO),
        Spacer(1, 1.5 * mm),
        pdf.campo('FECHA:', fecha, ancho_linea=ANCHO_LINEA_DATO, alto=4.6 * mm, compacto=True),
        pdf.campo('SOLICITADO POR:', cabecera.solicitado_por,
                  ancho_linea=ANCHO_LINEA_DATO, alto=4.6 * mm, compacto=True),
    ]
    if not es_ingreso:
        izquierda.append(
            pdf.campo('ENTREGADO POR:', cabecera.entregado_por,
                      ancho_linea=ANCHO_LINEA_DATO, alto=4.6 * mm, compacto=True)
        )

    ancho_casillas = 30 * mm
    return pdf.sin_bordes(Table(
        # Un ingreso solo de Bodega Técnica no trae tipo de transacción (esas
        # casillas son de la boleta de venta): quedan todas sin marcar, como
        # en el papel cuando no aplica ninguna.
        [[izquierda, pdf.casillas(OPCIONES_TIPO, getattr(cabecera, 'tipo_transaccion', ''), compacto=True)]],
        colWidths=[ANCHO_UTIL - ancho_casillas, ancho_casillas],
    ))


def _pie_de_salida(cabecera):
    """
    Solo FO-SE-012 lo trae. En el papel son dos columnas de tres renglones:
    a la izquierda factura/envío/devuelto por, a la derecha las tres firmas.

    Antes iban en dos bandas a lo ancho de la hoja —los campos en una fila y
    las firmas en otra— y ocupaban casi el doble de alto, que era parte de por
    qué la boleta entraba con tres renglones menos que la de papel.
    """
    ancho_columna = ANCHO_UTIL / 2
    ancho_linea = ancho_columna - 30 * mm

    izquierda = [
        pdf.campo('No. FACTURA', cabecera.no_factura, ancho_linea=ancho_linea,
                  alto=ALTO_PIE, compacto=True, ancho_etiqueta=24 * mm),
        pdf.campo('ENVÍO Y/O RECIBO', cabecera.envio_recibo, ancho_linea=ancho_linea,
                  alto=ALTO_PIE, compacto=True, ancho_etiqueta=24 * mm),
        pdf.campo('DEVUELTO POR:', cabecera.devuelto_por, ancho_linea=ancho_linea,
                  alto=ALTO_PIE, compacto=True, ancho_etiqueta=24 * mm),
    ]
    # Las firmas son campos vacíos con su rótulo: en el papel se llenan a mano
    # sobre la misma línea, no en un recuadro aparte.
    derecha = [
        pdf.campo('NOMBRE Y FIRMA AUT:', '', ancho_linea=ancho_linea,
                  alto=ALTO_PIE, compacto=True, ancho_etiqueta=30 * mm),
        pdf.campo('NOMBRE Y FIRMA REC:', '', ancho_linea=ancho_linea,
                  alto=ALTO_PIE, compacto=True, ancho_etiqueta=30 * mm),
        pdf.campo('NOMBRE Y FIRMA DEV:', '', ancho_linea=ancho_linea,
                  alto=ALTO_PIE, compacto=True, ancho_etiqueta=30 * mm),
    ]

    return [
        Spacer(1, 1.5 * mm),
        KeepTogether(pdf.sin_bordes(Table(
            [[izquierda, derecha]], colWidths=[ancho_columna] * 2,
        ))),
    ]


def _pagina(cabecera, lineas, es_ingreso, numero, total):
    titulo = 'INGRESO A BODEGA' if es_ingreso else 'SALIDA DE BODEGA'
    codigo = 'FO-SE-013' if es_ingreso else 'FO-SE-012'
    encabezados, anchos = COLUMNAS_INGRESO if es_ingreso else COLUMNAS_SALIDA

    alto_fila = ALTO_FILA_INGRESO if es_ingreso else ALTO_FILA_SALIDA

    elementos = [
        pdf.bloque_encabezado(
            titulo,
            f'Código: {codigo}<br/>Versión: {VERSION}',
            f'Página {numero} de {total}',
            ANCHO_UTIL,
            compacto=True,
        ),
        Spacer(1, 2 * mm),
        _datos_y_casillas(cabecera, es_ingreso),
        Spacer(1, 2 * mm),
        pdf.tabla_de_detalle(
            encabezados, _filas(lineas, es_ingreso), anchos,
            FILAS_POR_PAGINA, alto_fila, compacto=True,
        ),
    ]

    # La observación no viene impresa en el talonario, pero si el operador
    # escribió una hay que llevarla a la boleta o se pierde al imprimir.
    if cabecera.observacion and numero == total:
        elementos += [
            Spacer(1, 1.5 * mm),
            Paragraph(f'<b>OBSERVACIÓN:</b> {cabecera.observacion}', pdf.CELDA_CHICA),
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
    lineas = documentos.lineas_del_documento(folio)
    if not lineas:
        raise MovimientoVenta.DoesNotExist(f'No hay ningún documento con folio {folio}.')

    cabecera = lineas[0].movimiento
    es_ingreso = documentos.es_ingreso(lineas)

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
