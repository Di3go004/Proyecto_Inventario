from django import forms
from django.utils import timezone

from core.forms import CampoProveedor, solo_el_nombre
from core.models import Proveedor

from .models import Articulo, MovimientoVenta


class ArticuloForm(forms.ModelForm):
    # Escribible: al comprarle a un proveedor nuevo no hay que salirse del
    # formulario a darlo de alta primero. Ver core.forms.CampoProveedor.
    proveedor = CampoProveedor()

    class Meta:
        model = Articulo
        # stock_actual NO se incluye: se calcula solo desde los movimientos
        # (RF-08), nunca se edita a mano desde el catálogo.
        fields = [
            'codigo_interno', 'numero_serie', 'nombre_producto', 'marca', 'modelo',
            'capacidad', 'bodega', 'categoria', 'proveedor', 'precio', 'imagen', 'imagen_url',
            'stock_optimo', 'stock_alerta', 'stock_critico', 'activo',
        ]
        # codigo_interno queda opcional a propósito: si se deja vacío, se
        # genera solo como SE-MODELO-CAPACIDAD al guardar (Articulo.save()).
        # Dejarlo vacío también sirve para regenerarlo al editar.
        widgets = {
            'codigo_interno': forms.TextInput(attrs={
                'placeholder': 'Vacío = se genera solo (SE-MODELO-CAPACIDAD)',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        solo_el_nombre(self.fields['categoria'])

    def clean(self):
        datos = super().clean()
        optimo = datos.get('stock_optimo')
        alerta = datos.get('stock_alerta')
        critico = datos.get('stock_critico')
        if None not in (optimo, alerta, critico):
            if not (critico <= alerta <= optimo):
                raise forms.ValidationError(
                    'Los umbrales deben cumplir: crítico ≤ alerta ≤ óptimo.'
                )
        return datos

    def clean_imagen(self):
        imagen = self.cleaned_data.get('imagen')
        if imagen and imagen.size > 5 * 1024 * 1024:
            raise forms.ValidationError('La imagen no puede pesar más de 5 MB.')
        return imagen


class EntradaFechaHora(forms.DateTimeInput):
    """
    <input type="datetime-local">: usa el calendario que ya trae el
    navegador, sin librerías externas. Importa porque el sistema corre en la
    red local de la empresa y muchas veces sin salida a internet (RNF-01).
    """

    input_type = 'datetime-local'

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format='%Y-%m-%dT%H:%M')


class DocumentoMovimientoForm(forms.Form):
    """
    Cabecera de un documento de bodega (RF-05).

    Una boleta de papel —FO-SE-013 de ingreso o FO-SE-012 de salida— lleva
    varias líneas de producto bajo un mismo encabezado. Aquí se captura ese
    encabezado una sola vez y se copia a cada MovimientoVenta que comparte
    el folio; las líneas se leen aparte con leer_lineas().
    """

    # "Ajuste / Saldo inicial" no se ofrece: lo pone la carga masiva al
    # importar (RF-09), no es algo que se registre a mano en una boleta.
    TIPOS_VISIBLES = [
        (valor, etiqueta) for valor, etiqueta in MovimientoVenta.TipoTransaccion.choices
        if valor != MovimientoVenta.TipoTransaccion.AJUSTE_INICIAL
    ]

    # Campos que solo existen en uno de los dos documentos.
    SOLO_SALIDA = ('entregado_por', 'cliente_nombre', 'envio_recibo')

    folio = forms.CharField(
        max_length=30, required=False, label='Folio de la boleta',
        help_text='El número que trae la boleta de papel. Se propone el '
                  'siguiente de la serie; cámbialo si el talonario va en otro.',
    )
    fecha = forms.DateTimeField(label='Fecha del movimiento', widget=EntradaFechaHora())
    tipo_transaccion = forms.ChoiceField(choices=TIPOS_VISIBLES, label='Tipo de movimiento')
    solicitado_por = forms.CharField(max_length=150, label='Solicitado por')
    entregado_por = forms.CharField(max_length=150, required=False, label='Entregado por')
    cliente_nombre = forms.CharField(max_length=150, required=False, label='Cliente')
    no_factura = forms.CharField(max_length=50, required=False, label='No. de factura')
    no_boleta = forms.CharField(max_length=50, required=False, label='No. de boleta')
    envio_recibo = forms.CharField(max_length=100, required=False, label='Envío / recibo')
    observacion = forms.CharField(
        required=False, label='Observación', widget=forms.Textarea(attrs={'rows': 2}),
    )

    def __init__(self, *args, tipo_documento, folio_sugerido='', **kwargs):
        """
        El folio se escribe a mano: lo trae impreso el talonario de papel y es
        ese el que tiene que quedar guardado. El sistema propone el siguiente
        de la serie para no tener que teclearlo cuando van en orden, pero
        cualquiera puede cambiarlo.

        (Antes era automático y solo el administrador podía sobrescribirlo,
        escondido en un desplegable.)
        """
        super().__init__(*args, **kwargs)
        self.tipo_documento = tipo_documento
        es_ingreso = tipo_documento == MovimientoVenta.TipoDocumento.INGRESO

        if es_ingreso:
            for nombre in self.SOLO_SALIDA:
                del self.fields[nombre]

        if es_ingreso:
            self.fields['no_boleta'].label = 'Boleta de ingreso a bodega'
        else:
            self.fields['no_boleta'].label = 'Boleta de salida'

        if not self.is_bound:
            # Por defecto "ahora", que es el caso normal; el operador solo la
            # cambia cuando está digitando una boleta de días anteriores.
            self.fields['fecha'].initial = timezone.now()
            self.fields['folio'].initial = folio_sugerido

    def datos_para_movimiento(self):
        """Los campos de cabecera tal como se guardan en cada línea."""
        datos = dict(self.cleaned_data)
        datos.pop('folio', None)
        datos.pop('tipo_transaccion', None)
        return datos


class DevolucionDemoForm(forms.Form):
    """
    RF-06: cierra una salida de préstamo/demo. Al guardarse, el artículo
    vuelve a contar en el stock porque el equipo regresó físicamente.
    """

    fecha_devolucion = forms.DateTimeField(label='Fecha de devolución', widget=EntradaFechaHora())
    devuelto_por = forms.CharField(max_length=150, label='Devuelto por')
    observacion = forms.CharField(
        required=False, label='Observación', widget=forms.Textarea(attrs={'rows': 2}),
    )

    def __init__(self, *args, movimiento=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.movimiento = movimiento
        if not self.is_bound:
            self.fields['fecha_devolucion'].initial = timezone.now()

    def clean_fecha_devolucion(self):
        fecha = self.cleaned_data['fecha_devolucion']
        if self.movimiento and fecha < self.movimiento.fecha:
            raise forms.ValidationError(
                'La devolución no puede ser anterior a la salida '
                f'({timezone.localtime(self.movimiento.fecha):%d/%m/%Y %H:%M}).'
            )
        return fecha


LIMITE_LINEAS = 40

# El buscador del FO-SE-013 ofrece los dos catálogos, así que el id de una
# línea tiene que decir de cuál salió: el 12 de Bodega 1 y 2 no es el 12 de
# Bodega Técnica.
PREFIJO_VENTAS = 'art-'
PREFIJO_TECNICA = 'act-'


def identificador_de(producto, es_tecnica):
    """El id con prefijo que viaja en el formulario y en el buscador."""
    return f'{PREFIJO_TECNICA if es_tecnica else PREFIJO_VENTAS}{producto.pk}'


def _resolver_producto(identificador, texto, incluir_tecnica):
    """
    Encuentra el producto de una línea. Devuelve (objeto, es_tecnica).

    El identificador viene del buscador con un prefijo que dice de qué
    catálogo salió: "art-12" es de Bodega 1 y 2, "act-34" de Bodega Técnica.
    Hace falta porque el FO-SE-013 es el mismo formato para las tres bodegas
    y la misma pantalla ofrece los dos catálogos: sin el prefijo, el id 12
    sería ambiguo.

    Un identificador sin prefijo se toma como de Bodega 1 y 2, que es como
    se guardaba antes de que Bodega Técnica llevara existencia.
    """
    from tecnica.models import Activo

    if identificador.startswith(PREFIJO_TECNICA):
        if not incluir_tecnica:
            return None, True
        crudo = identificador[len(PREFIJO_TECNICA):]
        activo = Activo.objects.filter(pk=int(crudo)).first() if crudo.isdigit() else None
        return activo, True

    crudo = identificador[len(PREFIJO_VENTAS):] if identificador.startswith(PREFIJO_VENTAS) else identificador
    articulo = Articulo.objects.filter(pk=int(crudo)).first() if crudo.isdigit() else None
    if articulo is not None:
        return articulo, False

    # Se escribió el código completo y se pasó al siguiente campo sin tocar
    # la lista de sugerencias: igual se acepta, que es como se va a capturar
    # más rápido en bodega (RF-13).
    if texto:
        articulo = Articulo.objects.filter(codigo_interno__iexact=texto).first()
        if articulo is not None:
            return articulo, False
        if incluir_tecnica:
            activo = Activo.objects.filter(codigo_interno__iexact=texto).first()
            if activo is not None:
                return activo, True

    return None, False


def leer_lineas(post, incluir_tecnica=False):
    """
    Interpreta las líneas de producto de un documento (los campos
    linea_articulo[] / linea_cantidad[] / linea_texto[] del formulario).

    Devuelve una lista de diccionarios con lo que el usuario escribió más
    el producto resuelto o el error de esa línea, para poder volver a pintar
    la tabla tal cual quedó en vez de hacerle empezar de nuevo.

    `incluir_tecnica` habilita los activos de Bodega Técnica. Solo se activa
    en el ingreso: a esa bodega únicamente entran cosas, la existencia baja
    dando de baja, y no hay salida que registrar en el FO-SE-012.
    """
    identificadores = post.getlist('linea_articulo')
    cantidades = post.getlist('linea_cantidad')
    textos = post.getlist('linea_texto')

    lineas = []
    for indice, identificador in enumerate(identificadores[:LIMITE_LINEAS]):
        identificador = (identificador or '').strip()
        cantidad_texto = (cantidades[indice] if indice < len(cantidades) else '').strip()
        texto = (textos[indice] if indice < len(textos) else '').strip()

        # Fila completamente vacía: se ignora en silencio (siempre queda una
        # de más al final para poder seguir agregando).
        if not identificador and not cantidad_texto and not texto:
            continue

        linea = {
            'texto': texto, 'articulo_id': identificador,
            'cantidad_texto': cantidad_texto, 'articulo': None,
            'es_tecnica': False, 'cantidad': None, 'error': '',
        }

        producto, es_tecnica = _resolver_producto(identificador, texto, incluir_tecnica)

        if producto is None:
            linea['error'] = 'No se encontró el producto. Elígelo de las sugerencias.'
        elif not es_tecnica and not producto.activo:
            linea['error'] = f'"{producto.nombre_producto}" está marcado como inactivo.'
        else:
            linea['articulo'] = producto
            linea['es_tecnica'] = es_tecnica
            linea['articulo_id'] = identificador_de(producto, es_tecnica)
            linea['texto'] = texto or producto.codigo_interno

        if not linea['error']:
            try:
                cantidad = int(cantidad_texto)
            except ValueError:
                linea['error'] = 'La cantidad debe ser un número entero.'
            else:
                if cantidad <= 0:
                    linea['error'] = 'La cantidad tiene que ser mayor que cero.'
                else:
                    linea['cantidad'] = cantidad

        lineas.append(linea)

    return lineas
