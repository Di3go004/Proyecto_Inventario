from django.urls import path

from . import views

urlpatterns = [
    path('catalogo/ventas/', views.catalogo_articulos, name='catalogo_articulos'),
    path('catalogo/ventas/nuevo/', views.articulo_nuevo, name='articulo_nuevo'),
    path('catalogo/ventas/<int:pk>/', views.articulo_detalle, name='articulo_detalle'),
    path('catalogo/ventas/<int:pk>/editar/', views.articulo_editar, name='articulo_editar'),
    path('catalogo/ventas/<int:pk>/eliminar/', views.articulo_eliminar, name='articulo_eliminar'),
    path('catalogo/ventas/<int:pk>/kardex/', views.kardex_articulo, name='kardex_articulo'),
    path('catalogo/ventas/carga-masiva/', views.carga_masiva_subir, name='carga_masiva_subir'),
    path('catalogo/ventas/carga-masiva/mapear/', views.carga_masiva_mapear, name='carga_masiva_mapear'),
    path('catalogo/ventas/carga-masiva/cancelar/', views.carga_masiva_cancelar, name='carga_masiva_cancelar'),

    # Fase 3 — movimientos (RF-05, RF-06)
    path('movimientos/ventas/', views.movimientos_ventas, name='movimientos_ventas'),
    path('movimientos/ventas/ingreso/', views.movimiento_ingreso, name='movimiento_ingreso'),
    path('movimientos/ventas/salida/', views.movimiento_salida, name='movimiento_salida'),
    path('movimientos/ventas/documento/<str:folio>/', views.documento_detalle, name='documento_detalle'),
    path('movimientos/ventas/<int:pk>/devolucion/', views.devolucion_demo, name='devolucion_demo'),

    # RF-13 — sugerencias del buscador (lo consume static/js/autocompletar.js)
    path('api/ventas/articulos/', views.api_buscar_articulos, name='api_buscar_articulos'),
]
