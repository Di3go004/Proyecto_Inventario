from django import forms
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from .models import Categoria, Proveedor


def solo_el_nombre(campo_categoria):
    """
    Quita el "(Ventas)" / "(Técnica)" de las opciones del desplegable.

    El __str__ de Categoria lo incluye porque en una lista mezclada hace
    falta, pero en el catálogo el campo ya está filtrado a una sola bodega
    (limit_choices_to) y el sufijo se repite idéntico en todas las opciones.
    """
    campo_categoria.label_from_instance = lambda categoria: categoria.nombre


class CategoriaForm(forms.ModelForm):
    """
    El módulo no se puede cambiar una vez creada: una categoría de Bodega 1
    y 2 movida a Técnica dejaría a sus artículos apuntando a una categoría
    que su propio campo ya no admite (el FK filtra por módulo). Para eso se
    crea otra y se reasignan.
    """

    class Meta:
        model = Categoria
        fields = ['nombre', 'modulo']
        labels = {'modulo': 'Bodega'}
        help_texts = {
            'nombre': 'Como lo llaman en la bodega. Ej.: "Celdas de carga".',
            'modulo': 'Ventas = Bodega 1 y 2. Técnica = herramienta de uso interno.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['modulo'].disabled = True
            self.fields['modulo'].help_text = (
                'No se puede cambiar: sus artículos dejarían de poder usarla. '
                'Crea otra en la otra bodega y reasígnalos.'
            )

    def clean_nombre(self):
        # Los espacios de las puntas los quita Django solo; lo que falta es
        # juntar los de en medio, que es lo que pasa al pegar un nombre desde
        # el Excel: "Celdas  de   carga" y "Celdas de carga" entrarían como
        # dos categorías distintas y en la lista se verían idénticas.
        return ' '.join(self.cleaned_data['nombre'].split())

    def clean(self):
        datos = super().clean()
        nombre = datos.get('nombre')
        # disabled=True hace que el módulo no venga en el POST al editar, así
        # que se toma el que ya tiene guardado.
        modulo = datos.get('modulo') or self.instance.modulo
        if not nombre or not modulo:
            return datos

        repetida = Categoria.objects.filter(nombre__iexact=nombre, modulo=modulo)
        if self.instance.pk:
            repetida = repetida.exclude(pk=self.instance.pk)
        if repetida.exists():
            raise forms.ValidationError(
                f'Ya existe una categoría "{nombre}" en esa bodega.'
            )
        return datos


class EntradaConSugerencias(forms.TextInput):
    """
    Caja de texto que arrastra su propio <datalist> con las sugerencias.

    Se pinta sola en vez de pedirle a cada plantilla que agregue la lista:
    el campo se usa en dos formularios y se olvidaría en el tercero. El
    <datalist> es HTML puro, así que funciona sin librerías ni internet
    (RNF-01) y en celular el teclado sugiere igual.
    """

    def __init__(self, sugerencias, attrs=None):
        super().__init__(attrs)
        self.sugerencias = sugerencias

    def render(self, name, value, attrs=None, renderer=None):
        lista = f'sugerencias-{name}'
        attrs = {**(attrs or {}), 'list': lista, 'autocomplete': 'off'}
        caja = super().render(name, value, attrs, renderer)
        opciones = format_html_join(
            '', '<option value="{}"></option>', ((s,) for s in self.sugerencias()),
        )
        return mark_safe(caja + format_html('<datalist id="{}">{}</datalist>', lista, opciones))


class CampoProveedor(forms.CharField):
    """
    Proveedor escribible, con la lista de los que ya existen como sugerencia.

    Antes era un desplegable cerrado: al comprarle a alguien nuevo había que
    salirse del formulario a darlo de alta primero, y no había pantalla para
    hacerlo. Ahora se escribe el nombre y si no existe se crea solo.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('required', False)
        kwargs.setdefault('max_length', 150)
        kwargs.setdefault('label', 'Proveedor')
        kwargs.setdefault(
            'help_text',
            'Elige uno de la lista o escribe el nombre si es nuevo.',
        )
        kwargs.setdefault('widget', EntradaConSugerencias(self._nombres))
        super().__init__(*args, **kwargs)

    @staticmethod
    def _nombres():
        return Proveedor.objects.order_by('nombre').values_list('nombre', flat=True)

    def prepare_value(self, value):
        """
        Al editar, el ModelForm entrega el id del proveedor; en pantalla tiene
        que verse el nombre.
        """
        if isinstance(value, Proveedor):
            return value.nombre
        if value in (None, ''):
            return value
        try:
            pk = int(value)
        except (TypeError, ValueError):
            return value
        proveedor = Proveedor.objects.filter(pk=pk).first()
        return proveedor.nombre if proveedor else value

    def clean(self, value):
        """
        Devuelve el Proveedor, creándolo si hace falta.

        La búsqueda es sin distinguir mayúsculas para no terminar con
        "Brecknell" y "BRECKNELL" como dos proveedores distintos, que es
        justo lo que trae el Excel.
        """
        nombre = ' '.join((super().clean(value) or '').split())
        if not nombre:
            return None

        existente = Proveedor.objects.filter(nombre__iexact=nombre).first()
        if existente:
            return existente
        return Proveedor.objects.create(nombre=nombre)
