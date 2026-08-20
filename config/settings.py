"""
Configuración de Django para el Sistema de Control de Bodega.
Ver PLAN.md, REQUERIMIENTOS_FUNCIONALES.md y BASE_DATOS.sql para el contexto
de negocio detrás de estas decisiones.
"""

from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('DJANGO_SECRET_KEY')
DEBUG = config('DJANGO_DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = [h.strip() for h in config('DJANGO_ALLOWED_HOSTS', default='').split(',') if h.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Apps propias del sistema (ver PLAN.md → Modelo de datos)
    'usuarios',
    'core',
    'ventas',
    'tecnica',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Base de datos: PostgreSQL, siempre (ver PLAN.md → por qué no SQLite:
# varios usuarios concurrentes escribiendo movimientos a la vez).
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('POSTGRES_DB'),
        'USER': config('POSTGRES_USER'),
        'PASSWORD': config('POSTGRES_PASSWORD'),
        'HOST': config('POSTGRES_HOST', default='db'),
        'PORT': config('POSTGRES_PORT', default='5432'),
    }
}

# Modelo de usuario propio (rol: administrador/operador/contabilidad).
# Ver usuarios/models.py y RF-01/RF-04.
AUTH_USER_MODEL = 'usuarios.Usuario'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Guatemala: idioma, zona horaria (los reportes/kardex quedan con hora local).
LANGUAGE_CODE = 'es'
TIME_ZONE = 'America/Guatemala'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Fotos subidas desde el catálogo (artículos/activos). En el contenedor
# quedan dentro de /app/media, que por el bind mount del docker-compose
# también es la carpeta media/ del proyecto en el host — persisten solas,
# sin volumen aparte.
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Límite general de subida: lo manda la carga masiva de Excel (RF-09), esos
# archivos reales pesan hasta ~55 MB (fotos incrustadas por fila). El límite
# de 5 MB por foto de producto (RF del catálogo) se valida aparte, en
# ArticuloForm/ActivoForm — este de acá es solo el techo general del request.
FILE_UPLOAD_MAX_MEMORY_SIZE = 80 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 80 * 1024 * 1024

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'resumen'
LOGOUT_REDIRECT_URL = 'login'
