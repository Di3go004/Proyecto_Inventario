from django import forms
from django.db.models import Sum
from django.utils import timezone

from core.forms import CampoProveedor, solo_el_nombre
from ventas.forms import EntradaFechaHora

from .models import Activo, MovimientoActivo, PrestamoActivo


class ActivoForm(forms.ModelForm):
    proveedor = CampoProveedor()

    class Meta:
        model = Activo
        fields = [
            'codigo_interno', 'nombre_producto', 'marca', 'modelo',
            'categoria', 'bodega', 'proveedor', 'precio', 'imagen', 'imagen_url', 'estado',
            'es_consumible', 'stock_optimo', 'stock_alerta', 'stock_critico',
        ]

    # No es campo del modelo (Activo.existencia se calcula desde los
    # movimientos), pero sí se captura acá: la herramienta entra al catálogo
    # con la cantidad que hay, y en los consumibles la corrección de cantidad
    # se hace escribiéndola en vez de registrar una baja.
    existencia = forms.IntegerField(
        min_value=0, required=False, label='Cantidad en bodega',
    )

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        solo_el_nombre(self.fields['categoria'])
        self.usuario = usuario
        self.existencia_anterior = self.instance.existencia if self.instance.pk else 0

        if not self.instance.pk:
            # Un activo nace en 0, igual que un artículo de Bodega 1 y 2: la
            # cantidad entra con un ingreso (FO-SE-013), no escribiéndola en
            # el catálogo. Antes este campo se podía llenar al crear, y por
            # ahí entraron 218 cantidades sin boleta que las respaldara.
            #
            # La marca de consumible NO es una excepción a esto: solo permite
            # corregir la cantidad DESPUÉS, sobre un activo que ya existe.
            self.fields['existencia'].disabled = True
            self.fields['existencia'].help_text = (
                'Arranca en 0. La cantidad entra con un ingreso (FO-SE-013). '
                'Si es algo que se gasta, marcá "Es consumible" y vas a poder '
                'escribirla al editarlo.'
            )
        elif not self.instance.es_consumible:
            # En herramienta y equipo la existencia solo se mueve con un
            # ingreso (FO-SE-013) o con una baja: escribirla a mano acá
            # dejaría el historial diciendo otra cosa que el catálogo.
            self.fields['existencia'].disabled = True
            self.fields['existencia'].help_text = (
                'Se mueve con un ingreso o con una baja, no aquí. '
                'Márcalo como consumible si es algo que se gasta.'
            )
        else:
            self.fields['existencia'].help_text = (
                'Es consumible: se puede corregir aquí y queda como ajuste en el historial.'
            )

        if not self.is_bound:
            self.initial.setdefault('existencia', self.existencia_anterior)

    def clean_imagen(self):
        imagen = self.cleaned_data.get('imagen')
        if imagen and imagen.size > 5 * 1024 * 1024:
            raise forms.ValidationError('La imagen no puede pesar más de 5 MB.')
        return imagen

    def clean_existencia(self):
        """Un campo disabled no viaja en el POST: se conserva lo que ya había."""
        nueva = self.cleaned_data.get('existencia')
        if self.fields['existencia'].disabled or nueva is None:
            return self.existencia_anterior
        return nueva

    def clean(self):
        datos = super().clean()
        nueva = datos.get('existencia', self.existencia_anterior)
        afuera = self.instance.cantidad_afuera if self.instance.pk else 0
        if nueva is not None and nueva < afuera:
            raise forms.ValidationError(
                f'No puede quedar en {nueva}: hay {afuera} unidad(es) prestadas '
                'que todavía no regresan.'
            )
        return datos

    def save(self, commit=True):
        """
        El ajuste de existencia se guarda como movimiento, no escribiendo el
        campo: así el catálogo y el historial nunca dicen cosas distintas, y
        queda quién lo cambió y cuándo.
        """
        activo = super().save(commit=commit)
        if not commit:
            return activo

        nueva = self.cleaned_data.get('existencia')
        if nueva is None or nueva == self.existencia_anterior:
            return activo

        diferencia = nueva - self.existencia_anterior
        MovimientoActivo.objects.create(
            tipo=MovimientoActivo.Tipo.AJUSTE if diferencia > 0 else MovimientoActivo.Tipo.BAJA,
            activo=activo, cantidad=abs(diferencia), usuario=self.usuario,
            motivo=MovimientoActivo.Motivo.CONSUMIDO if diferencia < 0 else '',
            observacion=(
                'Saldo inicial al crear el activo.'
                if self.existencia_anterior == 0 and diferencia > 0
                else 'Corrección de cantidad desde el catálogo.'
            ),
        )
        activo.refresh_from_db()
        return activo


class PrestamoForm(forms.ModelForm):
    """
    RF-07: registra la salida de una herramienta (mitad izquierda de
    FO-SE-066). El activo se elige con el buscador con sugerencias, así que
    lo que viaja en el formulario es el id en un campo oculto; el texto que
    se escribió va aparte (activo_texto) y solo sirve para volver a pintar
    el buscador si algo falla.
    """

    class Meta:
        model = PrestamoActivo
        fields = ['activo', 'cantidad', 'solicitante', 'fecha_salida', 'entregado_por',
                  'estado_al_salir', 'observacion']
        widgets = {
            # La clase la busca static/js/autocompletar.js para saber dónde
            # dejar el id del activo elegido.
            'activo': forms.HiddenInput(attrs={'class': 'autocompletar-valor'}),
            'fecha_salida': EntradaFechaHora,
            'observacion': forms.Textarea(attrs={'rows': 2}),
        }
        labels = {
            'fecha_salida': 'Fecha de salida',
            'estado_al_salir': 'Estado con el que sale',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Lo que se dio de baja completo queda en existencia 0 y ya no se presta.
        self.fields['activo'].queryset = Activo.objects.filter(existencia__gt=0)
        self.fields['solicitante'].label = 'Solicitante (quién se lo lleva)'
        # Una herramienta siempre sale en algún estado, así que la opción
        # vacía sobra: se quita y se propone "buen estado", que es el caso
        # normal. Sin esto el formulario se rechazaba por un campo que el
        # operador no tenía motivo para tocar.
        self.fields['estado_al_salir'].choices = [
            opcion for opcion in self.fields['estado_al_salir'].choices if opcion[0]
        ]
        if not self.is_bound:
            # Se escribe en self.initial y no en fields[...].initial: en un
            # ModelForm lo que viene de la instancia manda sobre el initial
            # del campo, así que un valor puesto ahí nunca se vería.
            self.initial.setdefault('fecha_salida', timezone.now())
            self.initial.setdefault('estado_al_salir', Activo.Estado.BUEN_ESTADO)

    def clean_activo(self):
        activo = self.cleaned_data['activo']
        if activo.agotado:
            raise forms.ValidationError(
                f'"{activo.nombre_producto}" no tiene existencia: se dio de baja todo (RF-12).'
            )
        return activo

    def clean(self):
        """
        No se puede sacar más de lo disponible.

        Antes bastaba con que no hubiera otro préstamo abierto, porque cada
        activo era una unidad física. Ahora hay cantidad: de 10 bombillos,
        dos personas pueden llevar unidades a la vez, y lo que hay que
        cuidar es que entre todos no se pasen de lo que existe.
        """
        datos = super().clean()
        activo = datos.get('activo')
        cantidad = datos.get('cantidad')
        if not activo or not cantidad:
            return datos

        afuera = (
            PrestamoActivo.objects
            .filter(activo=activo, fecha_regreso__isnull=True)
            .exclude(pk=self.instance.pk)
            .aggregate(total=Sum('cantidad'))['total'] or 0
        )
        disponibles = activo.existencia - afuera
        if cantidad > disponibles:
            if afuera:
                raise forms.ValidationError(
                    f'Solo hay {disponibles} disponible(s) de "{activo.nombre_producto}": '
                    f'existen {activo.existencia} y {afuera} ya están afuera.'
                )
            raise forms.ValidationError(
                f'Solo hay {disponibles} de "{activo.nombre_producto}" en la bodega.'
            )
        return datos


class RegresoForm(forms.ModelForm):
    """
    RF-07: cierra el préstamo (mitad derecha de FO-SE-066). El estado con
    el que regresa se copia al activo — ver PrestamoActivo.save().
    """

    class Meta:
        model = PrestamoActivo
        fields = ['fecha_regreso', 'recibido_por', 'estado_al_regresar', 'observacion']
        widgets = {
            'fecha_regreso': EntradaFechaHora,
            'observacion': forms.Textarea(attrs={'rows': 2}),
        }
        labels = {
            'fecha_regreso': 'Fecha de regreso',
            'recibido_por': 'Recibido por',
            'estado_al_regresar': 'Estado con el que regresa',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre in ('fecha_regreso', 'recibido_por', 'estado_al_regresar'):
            self.fields[nombre].required = True
        if not self.is_bound:
            # Igual que en PrestamoForm: sobre un ModelForm hay que tocar
            # self.initial, porque los valores de la instancia (aquí vacíos,
            # el préstamo todavía no se cerró) pisan el initial del campo.
            self.initial['fecha_regreso'] = timezone.now()
            # Lo más común es que regrese igual que salió: se propone eso y
            # el operador solo lo cambia si viene dañada.
            self.initial['estado_al_regresar'] = self.instance.estado_al_salir

    def clean_fecha_regreso(self):
        fecha = self.cleaned_data['fecha_regreso']
        if fecha < self.instance.fecha_salida:
            raise forms.ValidationError(
                'El regreso no puede ser anterior a la salida '
                f'({timezone.localtime(self.instance.fecha_salida):%d/%m/%Y %H:%M}).'
            )
        return fecha


class BajaActivoForm(forms.Form):
    """
    Dar de baja: descartar unidades que ya no sirven (RF-12).

    Es lo único que baja la existencia de Bodega Técnica. No lleva boleta —
    no es una salida hacia nadie, es material que se retira— pero sí queda el
    registro de cuántas, por qué y quién.
    """

    cantidad = forms.IntegerField(min_value=1, label='¿Cuántas se dan de baja?')
    motivo = forms.ChoiceField(choices=MovimientoActivo.Motivo.choices, label='Motivo')
    fecha = forms.DateTimeField(label='Fecha', widget=EntradaFechaHora())
    observacion = forms.CharField(
        required=False, label='Observación', widget=forms.Textarea(attrs={'rows': 2}),
    )

    def __init__(self, *args, activo, **kwargs):
        super().__init__(*args, **kwargs)
        self.activo = activo
        if not self.is_bound:
            self.fields['fecha'].initial = timezone.now()

    def clean_cantidad(self):
        cantidad = self.cleaned_data['cantidad']
        # Se descarta de lo que está en bodega: lo prestado no se puede dar de
        # baja sin que primero regrese, o el historial diría que se descartó
        # algo que sigue en manos de alguien.
        disponibles = self.activo.disponibles
        if cantidad > disponibles:
            afuera = self.activo.cantidad_afuera
            if afuera:
                raise forms.ValidationError(
                    f'Solo hay {disponibles} en bodega: de las {self.activo.existencia} '
                    f'que existen, {afuera} están prestadas. Registra su regreso primero.'
                )
            raise forms.ValidationError(
                f'Solo hay {disponibles} de "{self.activo.nombre_producto}".'
            )
        return cantidad

    def guardar(self, usuario):
        return MovimientoActivo.objects.create(
            tipo=MovimientoActivo.Tipo.BAJA,
            activo=self.activo,
            cantidad=self.cleaned_data['cantidad'],
            motivo=self.cleaned_data['motivo'],
            fecha=self.cleaned_data['fecha'],
            observacion=self.cleaned_data['observacion'],
            usuario=usuario,
        )
