from django.contrib import admin

from .models import Articulo, MovimientoVenta


@admin.register(Articulo)
class ArticuloAdmin(admin.ModelAdmin):
    list_display = (
        'codigo_interno', 'nombre_producto', 'bodega', 'stock_actual',
        'nivel_alerta', 'precio', 'activo',
    )
    list_filter = ('bodega', 'categoria', 'activo')
    search_fields = ('codigo_interno', 'numero_serie', 'nombre_producto', 'marca', 'modelo')

    @admin.display(description='Nivel')
    def nivel_alerta(self, obj):
        return obj.nivel_alerta


@admin.register(MovimientoVenta)
class MovimientoVentaAdmin(admin.ModelAdmin):
    list_display = (
        'fecha', 'tipo_documento', 'tipo_transaccion', 'articulo', 'cantidad',
        'usuario', 'fecha_devolucion',
    )
    list_filter = ('tipo_documento', 'tipo_transaccion')
    search_fields = ('articulo__codigo_interno', 'articulo__nombre_producto', 'folio', 'no_factura')
    autocomplete_fields = ('articulo', 'proveedor')
