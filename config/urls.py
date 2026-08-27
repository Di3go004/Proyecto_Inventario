from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.views.static import serve as servir_archivo

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('core.urls')),
    path('', include('usuarios.urls')),
    path('', include('ventas.urls')),
    path('', include('tecnica.urls')),
]

# Las fotos subidas desde el catálogo las sirve Django también en producción.
# La documentación lo desaconseja para sitios de mucho tráfico, pero acá son
# 4–10 personas en una red local, y la alternativa sería montar un servidor de
# archivos aparte solo para las fotos de los productos. WhiteNoise no las
# cubre: se suben en caliente, no forman parte de los estáticos del proyecto.
urlpatterns += [
    re_path(
        r'^%s(?P<path>.*)$' % settings.MEDIA_URL.lstrip('/'),
        servir_archivo,
        {'document_root': settings.MEDIA_ROOT},
    ),
]
