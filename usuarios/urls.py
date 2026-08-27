from django.urls import path

from . import views

urlpatterns = [
    # RF-01 — gestión de usuarios, solo para el rol administrador
    path('usuarios/', views.lista_usuarios, name='lista_usuarios'),
    path('usuarios/nuevo/', views.usuario_nuevo, name='usuario_nuevo'),
    path('usuarios/<int:pk>/editar/', views.usuario_editar, name='usuario_editar'),
    path('usuarios/<int:pk>/clave/', views.usuario_clave, name='usuario_clave'),
    path('usuarios/<int:pk>/eliminar/', views.usuario_eliminar, name='usuario_eliminar'),
]
