from django.contrib import admin

from .models import Activo, PrestamoActivo


@admin.register(Activo)
class ActivoAdmin(admin.ModelAdmin):
    list_display = ('codigo_interno', 'nombre_producto', 'bodega', 'estado', 'precio', 'esta_prestado')
    list_filter = ('bodega', 'categoria', 'estado')
    search_fields = ('codigo_interno', 'nombre_producto', 'marca', 'modelo')

    @admin.display(description='Prestado', boolean=True)
    def esta_prestado(self, obj):
        return obj.esta_prestado


@admin.register(PrestamoActivo)
class PrestamoActivoAdmin(admin.ModelAdmin):
    list_display = (
        'activo', 'solicitante', 'fecha_salida', 'estado_al_salir',
        'fecha_regreso', 'estado_al_regresar', 'usuario',
    )
    list_filter = ('estado_al_salir', 'estado_al_regresar')
    search_fields = ('activo__codigo_interno', 'activo__nombre_producto', 'solicitante')
    autocomplete_fields = ('activo',)
