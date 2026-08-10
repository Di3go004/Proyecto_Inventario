from django.urls import path

from . import views

urlpatterns = [
    path('catalogo/ventas/', views.catalogo_articulos, name='catalogo_articulos'),
    path('catalogo/ventas/nuevo/', views.articulo_nuevo, name='articulo_nuevo'),
    path('catalogo/ventas/<int:pk>/', views.articulo_detalle, name='articulo_detalle'),
    path('catalogo/ventas/<int:pk>/editar/', views.articulo_editar, name='articulo_editar'),
    path('catalogo/ventas/<int:pk>/eliminar/', views.articulo_eliminar, name='articulo_eliminar'),
    path('catalogo/ventas/carga-masiva/', views.carga_masiva_subir, name='carga_masiva_subir'),
    path('catalogo/ventas/carga-masiva/mapear/', views.carga_masiva_mapear, name='carga_masiva_mapear'),
    path('catalogo/ventas/carga-masiva/cancelar/', views.carga_masiva_cancelar, name='carga_masiva_cancelar'),
]
