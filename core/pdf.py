"""
Piezas compartidas para generar las boletas en PDF (RF-10).

Se usa ReportLab y no una librería de HTML→PDF a propósito: los tres formatos
de la empresa son tablas regladas de ancho fijo, con filas en blanco para
seguir escribiendo a mano, y eso es justo lo que Platypus resuelve bien.
Además ReportLab es Python puro — no agrega paquetes del sistema a la imagen
de Docker ni al equipo donde se instale, que importa porque esto corre en una
PC de la oficina y sin internet (RNF-01).

Los PDF salen en tamaño carta para que se impriman 1:1 en cualquier impresora.
Los talonarios de papel son un poco más alargados, así que el formato no queda
milimétricamente igual, pero conserva la estructura, el folio y los espacios
de firma, que es lo que se necesita para archivarlo junto a los anteriores.
"""

from pathlib import Path

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, Table, TableStyle

EMPRESA = 'SOLUCIONES EXACTAS, S.A.'
RUTA_LOGO = Path(settings.BASE_DIR) / 'static' / 'img' / 'logo.png'

GRIS_ENCABEZADO = colors.Color(0.87, 0.87, 0.87)
LINEA = 0.75

# Alto de cada fila del detalle: suficiente para escribir a mano encima si en
# bodega necesitan corregir algo sobre la boleta ya impresa.
ALTO_FILA = 8.5 * mm


def _estilo(nombre, tamano, negrita=False, alineacion=0, interlineado=None):
    return ParagraphStyle(
        nombre,
        fontName='Helvetica-Bold' if negrita else 'Helvetica',
        fontSize=tamano,
        leading=interlineado or tamano + 2,
        alignment=alineacion,  # 0 izquierda, 1 centro, 2 derecha
    )


TITULO_EMPRESA = _estilo('empresa', 11, negrita=True, alineacion=1)
TITULO_FORMATO = _estilo('formato', 10, negrita=True, alineacion=1, interlineado=12)
META = _estilo('meta', 7)
FOLIO = _estilo('folio', 13, negrita=True)
ETIQUETA = _estilo('etiqueta', 8, negrita=True)
DATO = _estilo('dato', 8.5)
ENCABEZADO_TABLA = _estilo('encabezado_tabla', 7, negrita=True, alineacion=1, interlineado=8)
CELDA = _estilo('celda', 8)
CELDA_CENTRADA = _estilo('celda_centro', 8, alineacion=1)
CELDA_DERECHA = _estilo('celda_derecha', 8, alineacion=2)
PIE = _estilo('pie', 6.5)


def logo(alto=13 * mm):
    """El logo real de la empresa; si el archivo no está, se deja el hueco en
    blanco en vez de reventar la generación de la boleta."""
    if not RUTA_LOGO.exists():
        return ''
    imagen = Image(str(RUTA_LOGO))
    proporcion = imagen.imageWidth / imagen.imageHeight
    imagen.drawHeight = alto
    imagen.drawWidth = alto * proporcion
    return imagen


def bloque_encabezado(titulo, meta_arriba, meta_abajo, ancho_total):
    """
    La cabecera que comparten los tres formatos:

        +--------+---------------------------+---------------------+
        | LOGO   | SOLUCIONES EXACTAS, S.A.  | meta_arriba         |
        |        +---------------------------+---------------------+
        |        | (título del formato)      | meta_abajo          |
        +--------+---------------------------+---------------------+
    """
    ancho_logo = 24 * mm
    ancho_meta = 34 * mm
    ancho_centro = ancho_total - ancho_logo - ancho_meta

    tabla = Table(
        [
            [logo(), Paragraph(EMPRESA, TITULO_EMPRESA), Paragraph(meta_arriba, META)],
            ['', Paragraph(titulo, TITULO_FORMATO), Paragraph(meta_abajo, META)],
        ],
        colWidths=[ancho_logo, ancho_centro, ancho_meta],
        rowHeights=[9 * mm, 9 * mm],
    )
    tabla.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), LINEA, colors.black),
        ('SPAN', (0, 0), (0, 1)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('LEFTPADDING', (2, 0), (2, -1), 4),
    ]))
    return tabla


def tabla_de_detalle(encabezados, filas, anchos, filas_minimas, alto_fila=ALTO_FILA):
    """
    La tabla reglada del detalle. Se completa con filas vacías hasta
    `filas_minimas` para que la boleta impresa conserve el aspecto del
    talonario y quede espacio para anotar a mano.

    El alto NO se fija con rowHeights: ReportLab recorta el contenido que no
    cabe, y un producto de nombre largo salía pisando las líneas de la tabla.
    En su lugar se calcula el relleno vertical para que una fila de un solo
    renglón mida `alto_fila`; las que necesiten dos o tres renglones crecen
    solas sin desbordarse.
    """
    relleno = max(2, (alto_fila - CELDA.leading) / 2)

    datos = [[Paragraph(texto, ENCABEZADO_TABLA) for texto in encabezados]]
    datos.extend(filas)

    # El espacio duro (&nbsp;) le da a la fila vacía la misma altura que a una
    # con texto, sin imprimir nada.
    vacias = max(0, filas_minimas - len(filas))
    datos.extend([[Paragraph('&nbsp;', CELDA)] + [''] * (len(encabezados) - 1) for _ in range(vacias)])

    tabla = Table(datos, colWidths=anchos, repeatRows=1)
    tabla.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), LINEA, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), GRIS_ENCABEZADO),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 0), 5),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        ('TOPPADDING', (0, 1), (-1, -1), relleno),
        ('BOTTOMPADDING', (0, 1), (-1, -1), relleno),
    ]))
    return tabla


def campo(etiqueta, valor, ancho_linea=55 * mm, alto=6.5 * mm):
    """
    Una etiqueta con su valor sobre una línea, como en el papel:
    "FECHA: ____________". Si no hay valor, la línea queda en blanco para
    llenarla a mano.
    """
    tabla = Table(
        [[Paragraph(etiqueta, ETIQUETA), Paragraph(valor or '', DATO)]],
        colWidths=[32 * mm, ancho_linea],
        rowHeights=[alto],
    )
    tabla.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('LINEBELOW', (1, 0), (1, 0), LINEA, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))
    return tabla


def casillas(opciones, marcada):
    """
    El bloque de casillas del papel (Equipo venta / Equipo préstamo /
    Repuestos / Materiales-Otro), con una X en la que corresponde al tipo de
    movimiento registrado.

    `opciones` es una lista de (clave, etiqueta); `marcada` es la clave.
    """
    filas = [
        [Paragraph(etiqueta, META), Paragraph('X' if clave == marcada else '', CELDA_CENTRADA)]
        for clave, etiqueta in opciones
    ]
    tabla = Table(filas, colWidths=[28 * mm, 8 * mm], rowHeights=[5.5 * mm] * len(filas))
    tabla.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), LINEA, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (0, -1), 3),
    ]))
    return tabla


def linea_de_firma(etiqueta, ancho=70 * mm):
    """Espacio en blanco con su rótulo debajo, para firmar a mano."""
    tabla = Table(
        [[''], [Paragraph(etiqueta, META)]],
        colWidths=[ancho],
        rowHeights=[8 * mm, 4 * mm],
    )
    tabla.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (0, 0), LINEA, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('ALIGN', (0, 1), (0, 1), 'CENTER'),
    ]))
    return tabla


def sin_bordes(tabla):
    """Quita el relleno lateral de una tabla usada solo para maquetar."""
    tabla.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    return tabla
