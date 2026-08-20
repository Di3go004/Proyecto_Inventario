from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('core.urls')),
    path('', include('ventas.urls')),
    path('', include('tecnica.urls')),
]

if settings.DEBUG:
    # Solo en desarrollo: en producción esto lo sirve el propio servidor
    # web/proxy, no Django. Ver PLAN.md → Arquitectura propuesta.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
