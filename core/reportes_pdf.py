"""
Reportes para imprimir (RF-14).

La versión en papel de lo que ya se ve en pantalla y se baja a Excel. El Excel
es para trabajar los datos —filtrar, ordenar, sumar a gusto—; este es para
imprimir, firmar y archivar: con los totales ya hechos, agrupado por bodega y
en una letra que se lee sin lupa.

Va en carta horizontal porque el detalle lleva nueve columnas: en vertical, el
nombre del producto quedaba partido en tres o cuatro renglones.

Los datos salen de core/reportes.py, los mismos que usan la pantalla y el
Excel, para que los tres cuadren. Acá solo se acomodan en la hoja.
"""

import io
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core import fechas, pdf, reportes
from core.templatetags.chips import texto_nivel

HOJA = landscape(letter)                     # 279 × 216 mm
MARGEN = 12 * mm
MARGEN_ARRIBA = 16 * mm                      # deja lugar al encabezado corrido
MARGEN_ABAJO = 15 * mm                       # y al pie con el número de página
ANCHO_UTIL = HOJA[0] - 2 * MARGEN            # ≈ 255 mm

# Los colores de la pantalla, para que el papel se reconozca como del sistema.
# Impresos en blanco y negro quedan como grises distintos, así que nada
# depende solo del color: el nivel también va escrito.
AZUL = colors.HexColor('#202199')
TINTA = colors.HexColor('#14152b')
GRIS = colors.HexColor('#5b5f7d')
LINEA_SUAVE = colors.HexColor('#d5d7e3')
FONDO_ENCABEZADO = colors.HexColor('#e9ebf5')
FONDO_GRUPO = colors.HexColor('#f3f4f9')
COLOR_DE_NIVEL = {
    'critico': colors.HexColor('#a3271d'),
    'alerta': colors.HexColor('#93630f'),
    'normal': GRIS,
    'optimo': colors.HexColor('#1c7a4d'),
}


def _estilo(nombre, tamano, negrita=False, alineacion=0, color=TINTA, **extra):
    return ParagraphStyle(
        nombre,
        fontName='Helvetica-Bold' if negrita else 'Helvetica',
        fontSize=tamano,
        leading=tamano * 1.25,
        alignment=alineacion,  # 0 izquierda, 1 centro, 2 derecha
        textColor=color,
        **extra,
    )


EMPRESA = _estilo('rp_empresa', 8.5, negrita=True, color=AZUL)
TITULO = _estilo('rp_titulo', 16, negrita=True)
SUBTITULO = _estilo('rp_subtitulo', 9, color=GRIS)
META = _estilo('rp_meta', 8, alineacion=2, color=GRIS)
SECCION = _estilo('rp_seccion', 10, negrita=True, color=AZUL, spaceBefore=10, spaceAfter=5)
NOTA = _estilo('rp_nota', 7.5, color=GRIS, spaceAfter=5)
ENCABEZADO = _estilo('rp_encabezado', 6.8, negrita=True, color=GRIS)
ENCABEZADO_DERECHA = _estilo('rp_encabezado_der', 6.8, negrita=True, alineacion=2, color=GRIS)
CELDA = _estilo('rp_celda', 7.5)
CELDA_DERECHA = _estilo('rp_celda_der', 7.5, alineacion=2)
CELDA_NEGRITA = _estilo('rp_celda_neg', 7.5, negrita=True)
CELDA_NEGRITA_DERECHA = _estilo('rp_celda_neg_der', 7.5, negrita=True, alineacion=2)
# Código, marca y proveedor, un punto más chicos: los códigos de la empresa
# son largos ("SE-SE-10003N-1-000-g-x-20-mg") y en 8 puntos se partían en tres.
CELDA_CHICA = _estilo('rp_celda_chica', 7)
# La fila de una unidad va más chica, en gris y corrida a la derecha: se lee
# como parte de su producto, no como otro artículo.
UNIDAD = _estilo('rp_unidad', 7, color=GRIS, leftIndent=5)
UNIDAD_TEXTO = _estilo('rp_unidad_texto', 7, color=GRIS)
GRUPO = _estilo('rp_grupo', 8.5, negrita=True, color=AZUL)
MOSAICO_ETIQUETA = _estilo('rp_mosaico_etq', 6.8, negrita=True, color=GRIS)
MOSAICO_VALOR = _estilo('rp_mosaico_val', 12, negrita=True)


def _p(texto, estilo):
    """
    Un párrafo con el texto escapado. Paragraph interpreta etiquetas: de un
    producto llamado "Indicador <SE> 7600" se perdía el "<SE>" sin avisar, y
    uno con un "<" sin cerrar tumbaba el reporte entero, no solo su fila.
    """
    return Paragraph(escape(str(texto)), estilo)


def _quetzales(monto):
    return f'Q {monto:,.2f}'


def _numero(valor):
    return f'{valor:,}'


# ---------------------------------------------------------------------------
# La hoja: encabezado corrido y pie con "Página X de Y"
# ---------------------------------------------------------------------------

def _lienzo(titulo, filtros, generado):
    """
    Un Canvas que dibuja el pie y el encabezado corrido al final, cuando ya se
    sabe cuántas hojas son: "Página 2 de 7" no se puede escribir antes.
    Es la receta conocida de ReportLab: se guarda cada hoja y se dibujan todas
    en save().
    """

    class Lienzo(Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._hojas = []

        def showPage(self):
            self._hojas.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._hojas)
            for hoja in self._hojas:
                self.__dict__.update(hoja)
                self._decorar(total)
                super().showPage()
            super().save()

        def _decorar(self, total):
            ancho, _alto = self._pagesize
            numero = self._pageNumber
            self.saveState()
            self.setStrokeColor(LINEA_SUAVE)
            self.setLineWidth(0.6)
            self.setFont('Helvetica', 7)
            self.setFillColor(GRIS)

            y_pie = MARGEN_ABAJO - 7 * mm
            self.line(MARGEN, y_pie + 3.5 * mm, ancho - MARGEN, y_pie + 3.5 * mm)
            self.drawString(MARGEN, y_pie, f'{pdf.EMPRESA}  ·  {titulo}  ·  Generado el {generado}')
            self.drawRightString(ancho - MARGEN, y_pie, f'Página {numero} de {total}')

            # La primera hoja ya trae el encabezado grande; las demás, una línea
            # para que una hoja suelta diga de qué reporte es.
            if numero > 1:
                y_arriba = self._pagesize[1] - MARGEN_ARRIBA + 5 * mm
                self.drawString(MARGEN, y_arriba, f'{titulo}  ·  {filtros}')
                self.drawRightString(ancho - MARGEN, y_arriba, pdf.EMPRESA)
                self.line(MARGEN, y_arriba - 2 * mm, ancho - MARGEN, y_arriba - 2 * mm)
            self.restoreState()

    return Lienzo


def _encabezado(titulo, subtitulo, generado, generado_por):
    """Logo, empresa y título a la izquierda; cuándo y quién, a la derecha."""
    meta = f'Generado el {generado}'
    if generado_por:
        meta += f'<br/>por {escape(generado_por)}'
    texto = [
        Paragraph(escape(pdf.EMPRESA), EMPRESA),
        Spacer(1, 1.5 * mm),
        Paragraph(escape(titulo), TITULO),
        Spacer(1, 1.5 * mm),
        Paragraph(escape(subtitulo), SUBTITULO),
    ]
    ancho_logo = 24 * mm
    ancho_meta = 60 * mm
    tabla = Table(
        [[pdf.logo(17 * mm), texto, Paragraph(meta, META)]],
        colWidths=[ancho_logo, ANCHO_UTIL - ancho_logo - ancho_meta, ancho_meta],
    )
    tabla.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4 * mm),
        ('LINEBELOW', (0, 0), (-1, 0), 1.2, AZUL),
    ]))
    return tabla


def _estilo_de_tabla(extra=()):
    """Lo que comparten todas las tablas del reporte: limpias, sin rejilla."""
    return TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, 0), FONDO_ENCABEZADO),
        ('LINEBELOW', (0, 0), (-1, 0), 0.8, GRIS),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        *extra,
    ])


# ---------------------------------------------------------------------------
# Existencias y valorización
# ---------------------------------------------------------------------------

NIVELES = ('critico', 'alerta', 'normal', 'optimo')


def _resumen_por_bodega(filas, totales):
    encabezados = ['Bodega', 'Artículos', 'Unidades', 'Valorización',
                   *[texto_nivel(nivel) for nivel in NIVELES]]
    datos = [[_p(encabezados[0], ENCABEZADO)] + [_p(t, ENCABEZADO_DERECHA) for t in encabezados[1:]]]

    for fila in filas:
        datos.append([
            _p(fila['bodega'], CELDA),
            _p(_numero(fila['articulos']), CELDA_DERECHA),
            _p(_numero(fila['unidades']), CELDA_DERECHA),
            _p(_quetzales(fila['valor']), CELDA_DERECHA),
            *[_p(_numero(fila['niveles'][nivel]), CELDA_DERECHA) for nivel in NIVELES],
        ])
    if not filas:
        datos.append([_p('No hay artículos que coincidan con los filtros.', CELDA)] + [''] * 7)

    # Solo si hay más de una bodega. Filtrado a una, su fila ya es el total, y
    # un "Total Bodega 1 y 2" con lo de una sola diría algo que no es: en un
    # papel que se archiva, eso se lee como el total de las dos.
    con_total = len(filas) > 1
    if con_total:
        datos.append([
            _p('Total Bodega 1 y 2', CELDA_NEGRITA),
            _p(_numero(totales['articulos']), CELDA_NEGRITA_DERECHA),
            _p(_numero(totales['unidades']), CELDA_NEGRITA_DERECHA),
            _p(_quetzales(totales['valor']), CELDA_NEGRITA_DERECHA),
            *[
                _p(_numero(sum(fila['niveles'][nivel] for fila in filas)), CELDA_NEGRITA_DERECHA)
                for nivel in NIVELES
            ],
        ])

    resto = (ANCHO_UTIL - 70 * mm - 45 * mm) / 6
    tabla = Table(datos, colWidths=[70 * mm, resto, resto, 45 * mm, resto, resto, resto, resto])
    extra = [('LINEBELOW', (0, 1), (-1, -2 if con_total else -1), 0.5, LINEA_SUAVE)]
    if con_total:
        extra += [
            ('LINEABOVE', (0, -1), (-1, -1), 0.8, TINTA),
            ('BACKGROUND', (0, -1), (-1, -1), FONDO_GRUPO),
        ]
    if not filas:
        extra.append(('SPAN', (0, 1), (-1, 1)))
    tabla.setStyle(_estilo_de_tabla(extra))
    return tabla


def _mosaicos_tecnica(tecnica):
    """Los seis números de Bodega Técnica, como las tarjetas de la pantalla."""
    mosaicos = [
        ('VALORIZACIÓN', _quetzales(tecnica['valor'])),
        ('UNIDADES', _numero(tecnica['unidades'])),
        ('EN BUEN ESTADO', _numero(tecnica['buen_estado'])),
        ('PRÓXIMAS A REEMPLAZO', _numero(tecnica['proximo_a_reemplazo'])),
        ('EN MAL ESTADO', _numero(tecnica['mal_estado'])),
        ('AGOTADAS', _numero(tecnica['agotados'])),
    ]
    tabla = Table(
        [[[_p(etiqueta, MOSAICO_ETIQUETA), Spacer(1, 1.5 * mm), _p(valor, MOSAICO_VALOR)]
          for etiqueta, valor in mosaicos]],
        colWidths=[ANCHO_UTIL / len(mosaicos)] * len(mosaicos),
    )
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), FONDO_GRUPO),
        # Una raya blanca gruesa entre celdas las separa como tarjetas.
        ('LINEAFTER', (0, 0), (-2, -1), 5, colors.white),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    return tabla


# Columnas del detalle. Producto se lleva lo que sobra.
COLUMNAS_DETALLE = [
    # 40 mm: medido, caben en un renglón 177 de los 189 códigos del catálogo.
    ('Código', 40 * mm, ENCABEZADO),
    # Un serial de 14 dígitos con su sangría tiene que caber en un renglón.
    ('N.º de serial', 26 * mm, ENCABEZADO),
    ('Producto', None, ENCABEZADO),
    ('Marca / Modelo', 32 * mm, ENCABEZADO),
    ('Proveedor', 26 * mm, ENCABEZADO),
    ('Existencia', 15 * mm, ENCABEZADO_DERECHA),
    ('Precio unitario', 20 * mm, ENCABEZADO_DERECHA),
    ('Valor total', 24 * mm, ENCABEZADO_DERECHA),
    ('Nivel', 13 * mm, ENCABEZADO),
]
_FIJAS = sum(ancho for _t, ancho, _e in COLUMNAS_DETALLE if ancho)
ANCHOS_DETALLE = [ancho or ANCHO_UTIL - _FIJAS for _t, ancho, _e in COLUMNAS_DETALLE]
ULTIMA = len(COLUMNAS_DETALLE) - 1


def _detalle(filas, detalle, totales):
    """
    Una tabla sola, agrupada por bodega: el renglón de la bodega, sus
    productos —cada uno con sus unidades debajo— y el total de la bodega.

    Una tabla y no una por bodega para que el encabezado de columnas se repita
    solo en cada hoja.
    """
    por_bodega = {fila['bodega']: fila for fila in filas}
    datos = [[_p(titulo, estilo) for titulo, _a, estilo in COLUMNAS_DETALLE]]
    estilo = []

    def total_de_bodega(nombre):
        fila = por_bodega[nombre]
        datos.append([
            _p(f'Total {nombre}', CELDA_NEGRITA), '', '', '', '',
            _p(_numero(fila['unidades']), CELDA_NEGRITA_DERECHA),
            '',
            _p(_quetzales(fila['valor']), CELDA_NEGRITA_DERECHA),
            '',
        ])
        n = len(datos) - 1
        estilo.extend([
            ('SPAN', (0, n), (4, n)),
            ('LINEABOVE', (0, n), (-1, n), 0.8, TINTA),
            ('BACKGROUND', (0, n), (-1, n), FONDO_GRUPO),
            ('TOPPADDING', (0, n), (-1, n), 4),
            ('BOTTOMPADDING', (0, n), (-1, n), 4),
        ])

    bodega_actual = None
    filas_desglosadas = reportes.desglosar_existencias(detalle)
    for indice, fila in enumerate(filas_desglosadas):
        articulo = fila.articulo
        nombre_bodega = articulo.bodega.nombre

        if nombre_bodega != bodega_actual:
            if bodega_actual is not None:
                total_de_bodega(bodega_actual)
            bodega_actual = nombre_bodega
            resumen = por_bodega[nombre_bodega]
            datos.append([_p(
                f"{nombre_bodega}  ·  {_numero(resumen['articulos'])} artículo(s)  ·  "
                f"{_numero(resumen['unidades'])} unidad(es)", GRUPO,
            )] + [''] * ULTIMA)
            n = len(datos) - 1
            estilo.extend([
                ('SPAN', (0, n), (-1, n)),
                ('BACKGROUND', (0, n), (-1, n), FONDO_GRUPO),
                ('TOPPADDING', (0, n), (-1, n), 5),
                ('BOTTOMPADDING', (0, n), (-1, n), 5),
                # El nombre de la bodega no se queda solo al pie de una hoja.
                ('NOSPLIT', (0, n), (-1, n + 1)),
            ])

        if fila.es_producto:
            nivel = fila.nivel
            datos.append([
                _p(articulo.codigo_interno, CELDA_CHICA),
                _p(fila.serial, CELDA),
                _p(articulo.nombre_producto, CELDA),
                _p(f'{articulo.marca} {articulo.modelo}'.strip(), CELDA_CHICA),
                _p(articulo.proveedor or '', CELDA_CHICA),
                _p(_numero(fila.existencia), CELDA_DERECHA),
                _p(_quetzales(fila.precio), CELDA_DERECHA),
                _p(_quetzales(fila.valor), CELDA_DERECHA),
                Paragraph(
                    escape(texto_nivel(nivel)),
                    ParagraphStyle('rp_nivel', parent=CELDA_NEGRITA, fontSize=7.5,
                                   textColor=COLOR_DE_NIVEL.get(nivel, GRIS)),
                ),
            ])
            n = len(datos) - 1
            estilo.append(('LINEABOVE', (0, n), (-1, n), 0.5, LINEA_SUAVE))
            # El producto no se queda solo al pie de una hoja con todas sus
            # unidades en la siguiente: se lleva al menos las dos primeras. No
            # todas, porque uno con cuarenta no cabría en ninguna hoja.
            unidades = len(getattr(articulo, 'unidades_aca', []))
            if unidades:
                estilo.append(('NOSPLIT', (0, n), (-1, n + min(unidades, 2))))
        else:
            fecha = fechas.fecha(fila.fecha_de_ingreso) if fila.fecha_de_ingreso else ''
            entro = fila.entro_con_texto
            if entro and entro != 'Carga inicial':
                entro = f'Entró con la boleta {entro}'
            datos.append([
                '',
                _p(fila.serial, UNIDAD),
                _p('  ·  '.join(parte for parte in (entro, fecha) if parte), UNIDAD_TEXTO),
                '', '', '', '', '', '',
            ])
            n = len(datos) - 1
            estilo.extend([
                ('SPAN', (2, n), (4, n)),
                ('TOPPADDING', (0, n), (-1, n), 1),
                ('BOTTOMPADDING', (0, n), (-1, n), 1),
            ])
            # La última unidad de un producto deja un respiro antes del que sigue.
            siguiente = filas_desglosadas[indice + 1] if indice + 1 < len(filas_desglosadas) else None
            if siguiente is None or siguiente.es_producto:
                estilo.append(('BOTTOMPADDING', (0, n), (-1, n), 3))

    if bodega_actual is None:
        datos.append([_p('No hay artículos que coincidan con los filtros.', CELDA)] + [''] * ULTIMA)
        estilo.append(('SPAN', (0, 1), (-1, 1)))
    else:
        total_de_bodega(bodega_actual)
        # Con las dos bodegas, el total general cierra el detalle: quien lee
        # la última hoja no tiene que volver a la primera para encontrarlo.
        if len(por_bodega) > 1:
            datos.append([
                _p('Total Bodega 1 y 2', CELDA_NEGRITA), '', '', '', '',
                _p(_numero(totales['unidades']), CELDA_NEGRITA_DERECHA),
                '',
                _p(_quetzales(totales['valor']), CELDA_NEGRITA_DERECHA),
                '',
            ])
            n = len(datos) - 1
            estilo.extend([
                ('SPAN', (0, n), (4, n)),
                ('LINEABOVE', (0, n), (-1, n), 1.2, AZUL),
                ('BACKGROUND', (0, n), (-1, n), FONDO_ENCABEZADO),
                ('TOPPADDING', (0, n), (-1, n), 5),
                ('BOTTOMPADDING', (0, n), (-1, n), 5),
            ])

    tabla = Table(datos, colWidths=ANCHOS_DETALLE, repeatRows=1)
    tabla.setStyle(_estilo_de_tabla(estilo))
    return tabla


def existencias(filas, detalle, totales, tecnica, *, bodega='Todas', solo_activos=True,
                generado_por='', ahora=None):
    """
    El reporte de existencias y valorización en PDF, con la misma información
    que el Excel: el resumen por bodega, Bodega Técnica y el detalle por
    artículo con cada unidad debajo de su producto.

    Recibe lo que devuelven reportes.existencias() y
    reportes.valorizacion_tecnica(), igual que la pantalla.
    """
    titulo = 'Existencias y valorización'
    filtros = (
        f'Bodega: {bodega}  ·  '
        f"{'Solo artículos activos' if solo_activos else 'Activos e inactivos'}"
    )
    generado = fechas.fecha_hora(ahora or timezone.now())

    contenido = [
        _encabezado(titulo, f'Bodega 1 y 2  ·  {filtros}', generado, generado_por),
        Paragraph('Resumen por bodega', SECCION),
        _resumen_por_bodega(filas, totales),
        Paragraph('Bodega Técnica', SECCION),
        Paragraph(
            'Precio × existencia, igual que Bodega 1 y 2. Los préstamos no bajan la '
            'existencia: la herramienta sigue siendo de la bodega. No depende de los '
            'filtros de arriba.',
            NOTA,
        ),
        _mosaicos_tecnica(tecnica),
        Paragraph('Detalle por artículo', SECCION),
        Paragraph(
            'Debajo de cada producto que lleva número de serie van sus unidades en '
            'bodega, con la boleta con que entró cada una.',
            NOTA,
        ),
        _detalle(filas, detalle, totales),
    ]

    salida = io.BytesIO()
    documento = SimpleDocTemplate(
        salida, pagesize=HOJA,
        leftMargin=MARGEN, rightMargin=MARGEN,
        topMargin=MARGEN_ARRIBA, bottomMargin=MARGEN_ABAJO,
        title=titulo, author=pdf.EMPRESA,
    )
    documento.build(contenido, canvasmaker=_lienzo(titulo, filtros, generado))
    return salida.getvalue()
