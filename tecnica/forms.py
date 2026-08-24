from django import forms
from django.utils import timezone

from ventas.forms import EntradaFechaHora

from .models import Activo, PrestamoActivo


class ActivoForm(forms.ModelForm):
    class Meta:
        model = Activo
        fields = [
            'codigo_interno', 'nombre_producto', 'marca', 'modelo',
            'categoria', 'bodega', 'proveedor', 'precio', 'imagen', 'imagen_url', 'estado',
        ]

    def clean_imagen(self):
        imagen = self.cleaned_data.get('imagen')
        if imagen and imagen.size > 5 * 1024 * 1024:
            raise forms.ValidationError('La imagen no puede pesar más de 5 MB.')
        return imagen


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
        self.fields['activo'].queryset = Activo.objects.exclude(estado=Activo.Estado.DE_BAJA)
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
        if activo.estado == Activo.Estado.DE_BAJA:
            raise forms.ValidationError('Ese activo está dado de baja y no se puede prestar (RF-12).')
        # La base de datos ya lo impide con una restricción única, pero acá
        # el aviso sale como error del formulario y no como pantalla de error.
        if PrestamoActivo.objects.filter(activo=activo, fecha_regreso__isnull=True).exists():
            prestado_a = PrestamoActivo.objects.filter(
                activo=activo, fecha_regreso__isnull=True,
            ).values_list('solicitante', flat=True).first()
            raise forms.ValidationError(
                f'"{activo.nombre_producto}" ya está prestado a {prestado_a}. '
                'Registra primero su regreso.'
            )
        return activo


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
