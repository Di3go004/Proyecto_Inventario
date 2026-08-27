from django import forms

from .models import Categoria


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
