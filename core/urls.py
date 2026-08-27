from django.urls import path

from . import views

urlpatterns = [
    path('', views.resumen, name='resumen'),

    # Fase 5 — Reportes (RF-14). Cada uno acepta ?formato=excel para descargarlo.
    path('reportes/', views.indice_reportes, name='indice_reportes'),
    path('reportes/existencias/', views.reporte_existencias, name='reporte_existencias'),
    path('reportes/alertas/', views.reporte_alertas, name='reporte_alertas'),
    path('reportes/movimientos/', views.reporte_movimientos, name='reporte_movimientos'),
    path('reportes/prestamos/', views.reporte_prestamos, name='reporte_prestamos'),

    # Categorías del catálogo (RF-02/RF-03), solo administrador
    path('categorias/', views.lista_categorias, name='lista_categorias'),
    path('categorias/nueva/', views.categoria_nueva, name='categoria_nueva'),
    path('categorias/<int:pk>/editar/', views.categoria_editar, name='categoria_editar'),
    path('categorias/<int:pk>/eliminar/', views.categoria_eliminar, name='categoria_eliminar'),
]
