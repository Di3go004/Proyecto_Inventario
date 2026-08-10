from django import forms

from .models import Articulo


class ArticuloForm(forms.ModelForm):
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
