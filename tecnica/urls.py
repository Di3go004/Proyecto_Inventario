from django.urls import path

from . import views

urlpatterns = [
    path('catalogo/tecnica/', views.catalogo_activos, name='catalogo_activos'),
    path('catalogo/tecnica/nuevo/', views.activo_nuevo, name='activo_nuevo'),
    path('catalogo/tecnica/<int:pk>/', views.activo_detalle, name='activo_detalle'),
    path('catalogo/tecnica/<int:pk>/editar/', views.activo_editar, name='activo_editar'),
    path('catalogo/tecnica/<int:pk>/eliminar/', views.activo_eliminar, name='activo_eliminar'),
    path('catalogo/tecnica/carga-masiva/', views.carga_masiva_subir, name='carga_masiva_subir_tecnica'),
    path('catalogo/tecnica/carga-masiva/mapear/', views.carga_masiva_mapear, name='carga_masiva_mapear_tecnica'),
    path('catalogo/tecnica/carga-masiva/cancelar/', views.carga_masiva_cancelar, name='carga_masiva_cancelar_tecnica'),

    # Fase 3 — préstamos de herramienta (RF-07)
    path('movimientos/tecnica/', views.prestamos_tecnica, name='prestamos_tecnica'),
    path('movimientos/tecnica/nuevo/', views.prestamo_nuevo, name='prestamo_nuevo'),
    path('movimientos/tecnica/<int:pk>/regreso/', views.prestamo_regreso, name='prestamo_regreso'),

    # RF-13 — sugerencias del buscador
    path('api/tecnica/activos/', views.api_buscar_activos, name='api_buscar_activos'),
]
