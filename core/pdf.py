"""
Piezas compartidas para generar las boletas en PDF (RF-10).

Se usa ReportLab y no una librería de HTML→PDF a propósito: los tres formatos
de la empresa son tablas regladas de ancho fijo, con filas en blanco para
seguir escribiendo a mano, y eso es justo lo que Platypus resuelve bien.
Además ReportLab es Python puro — no agrega paquetes del sistema a la imagen
de Docker ni al equipo donde se instale, que importa porque esto corre en una
PC de la oficina y sin internet (RNF-01).

Cada formato sale en el tamaño real de su talonario, porque las boletas se
imprimen, se firman y se archivan junto a las de papel de los años
anteriores — si no calzan, no entran en el mismo folder:

  - FO-SE-013 / FO-SE-012 (Bodega 1 y 2) → media carta apaisada, 216 × 140 mm
  - FO-SE-066 (Bodega Técnica)           → carta vertical, 216 × 279 mm

Por eso hay dos juegos de estilos: los normales y los `_CHICO`/`_CHICA` para
media carta, donde hay 140 mm de alto en vez de 279 y la tipografía normal
dejaría espacio para dos o tres líneas de detalle.
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

# Versión reducida, para los formatos que van en media carta (FO-SE-013 y
# FO-SE-012). Ahí hay 140 mm de alto en vez de 216: con la tipografía normal
# entrarían dos o tres líneas de detalle y la boleta perdería el sentido.
TITULO_EMPRESA_CHICO = _estilo('empresa_chico', 9, negrita=True, alineacion=1)
TITULO_FORMATO_CHICO = _estilo('formato_chico', 8.5, negrita=True, alineacion=1, interlineado=10)
META_CHICA = _estilo('meta_chica', 6)
FOLIO_CHICO = _estilo('folio_chico', 9, negrita=True)
ETIQUETA_CHICA = _estilo('etiqueta_chica', 6.5, negrita=True)
DATO_CHICO = _estilo('dato_chico', 7)
ENCABEZADO_TABLA_CHICO = _estilo('encabezado_chico', 6, negrita=True, alineacion=1, interlineado=7)
CELDA_CHICA = _estilo('celda_chica', 7)
CELDA_CHICA_CENTRADA = _estilo('celda_chica_centro', 7, alineacion=1)
CELDA_CHICA_DERECHA = _estilo('celda_chica_derecha', 7, alineacion=2)


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


def bloque_encabezado(titulo, meta_arriba, meta_abajo, ancho_total, compacto=False):
    """
    La cabecera que comparten los tres formatos:

        +--------+---------------------------+---------------------+
        | LOGO   | SOLUCIONES EXACTAS, S.A.  | meta_arriba         |
        |        +---------------------------+---------------------+
        |        | (título del formato)      | meta_abajo          |
        +--------+---------------------------+---------------------+

    `compacto` la achica para los formatos de media carta.
    """
    ancho_logo = (18 if compacto else 24) * mm
    ancho_meta = (28 if compacto else 34) * mm
    ancho_centro = ancho_total - ancho_logo - ancho_meta
    alto = (6.5 if compacto else 9) * mm

    estilo_empresa = TITULO_EMPRESA_CHICO if compacto else TITULO_EMPRESA
    estilo_titulo = TITULO_FORMATO_CHICO if compacto else TITULO_FORMATO
    estilo_meta = META_CHICA if compacto else META

    tabla = Table(
        [
            [logo(alto * 1.5), Paragraph(EMPRESA, estilo_empresa), Paragraph(meta_arriba, estilo_meta)],
            ['', Paragraph(titulo, estilo_titulo), Paragraph(meta_abajo, estilo_meta)],
        ],
        colWidths=[ancho_logo, ancho_centro, ancho_meta],
        rowHeights=[alto, alto],
    )
    tabla.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), LINEA, colors.black),
        ('SPAN', (0, 0), (0, 1)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('LEFTPADDING', (2, 0), (2, -1), 4),
    ]))
    return tabla


def tabla_de_detalle(encabezados, filas, anchos, filas_minimas, alto_fila=ALTO_FILA, compacto=False):
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
    estilo_celda = CELDA_CHICA if compacto else CELDA
    estilo_encabezado = ENCABEZADO_TABLA_CHICO if compacto else ENCABEZADO_TABLA
    relleno = max(1.5, (alto_fila - estilo_celda.leading) / 2)

    datos = [[Paragraph(texto, estilo_encabezado) for texto in encabezados]]
    datos.extend(filas)

    # El espacio duro (&nbsp;) le da a la fila vacía la misma altura que a una
    # con texto, sin imprimir nada. Va en TODAS las columnas, no solo en la
    # primera: una celda con la cadena vacía no es un Paragraph, así que
    # ReportLab la mide con su tipografía por omisión —12 pt de interlineado
    # contra los 9 de la boleta— y la fila vacía salía un 12 % más alta que
    # las llenas. Se veía en la boleta impresa y, peor, hacía que una boleta
    # con pocas líneas se pasara a una segunda hoja mientras una llena cabía.
    vacias = max(0, filas_minimas - len(filas))
    fila_vacia = [Paragraph('&nbsp;', estilo_celda) for _ in encabezados]
    datos.extend([list(fila_vacia) for _ in range(vacias)])

    tabla = Table(datos, colWidths=anchos, repeatRows=1)
    relleno_encabezado = 2 if compacto else 5
    tabla.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), LINEA, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), GRIS_ENCABEZADO),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 0), relleno_encabezado),
        ('BOTTOMPADDING', (0, 0), (-1, 0), relleno_encabezado),
        ('TOPPADDING', (0, 1), (-1, -1), relleno),
        ('BOTTOMPADDING', (0, 1), (-1, -1), relleno),
    ]))
    return tabla


def campo(etiqueta, valor, ancho_linea=55 * mm, alto=6.5 * mm, compacto=False, ancho_etiqueta=None):
    """
    Una etiqueta con su valor sobre una línea, como en el papel:
    "FECHA: ____________". Si no hay valor, la línea queda en blanco para
    llenarla a mano.
    """
    tabla = Table(
        [[
            Paragraph(etiqueta, ETIQUETA_CHICA if compacto else ETIQUETA),
            Paragraph(valor or '', DATO_CHICO if compacto else DATO),
        ]],
        colWidths=[ancho_etiqueta or (26 if compacto else 32) * mm, ancho_linea],
        rowHeights=[alto],
    )
    tabla.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('LINEBELOW', (1, 0), (1, 0), LINEA, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))
    return tabla


def casillas(opciones, marcada, compacto=False):
    """
    El bloque de casillas del papel (Equipo venta / Equipo préstamo /
    Repuestos / Materiales-Otro), con una X en la que corresponde al tipo de
    movimiento registrado.

    `opciones` es una lista de (clave, etiqueta); `marcada` es la clave.
    """
    estilo_texto = META_CHICA if compacto else META
    estilo_marca = CELDA_CHICA_CENTRADA if compacto else CELDA_CENTRADA
    filas = [
        [Paragraph(etiqueta, estilo_texto), Paragraph('X' if clave == marcada else '', estilo_marca)]
        for clave, etiqueta in opciones
    ]
    anchos = [22 * mm, 6 * mm] if compacto else [28 * mm, 8 * mm]
    alto = (4.2 if compacto else 5.5) * mm
    tabla = Table(filas, colWidths=anchos, rowHeights=[alto] * len(filas))
    tabla.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), LINEA, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (0, -1), 3),
    ]))
    return tabla


def linea_de_firma(etiqueta, ancho=70 * mm, alto=8 * mm, compacto=False):
    """Espacio en blanco con su rótulo debajo, para firmar a mano."""
    tabla = Table(
        [[''], [Paragraph(etiqueta, META_CHICA if compacto else META)]],
        colWidths=[ancho],
        rowHeights=[alto, (3.6 if compacto else 4.5) * mm],
    )
    tabla.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (0, 0), LINEA, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        # Sin esto el rótulo se dibuja encima de la línea de firma: el relleno
        # que ReportLab pone por defecto (6pt arriba y abajo) es más alto que
        # la fila del rótulo, y el texto se sale hacia arriba.
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
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
