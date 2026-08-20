from django import forms

from .models import Activo


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
