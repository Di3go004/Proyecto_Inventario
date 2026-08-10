from django.urls import path

from . import views

urlpatterns = [
    path('catalogo/tecnica/', views.catalogo_activos, name='catalogo_activos'),
    path('catalogo/tecnica/nuevo/', views.activo_nuevo, name='activo_nuevo'),
    path('catalogo/tecnica/<int:pk>/editar/', views.activo_editar, name='activo_editar'),
    path('catalogo/tecnica/<int:pk>/eliminar/', views.activo_eliminar, name='activo_eliminar'),
]
