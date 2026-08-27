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

# Entrar escribiendo el usuario con o sin mayúsculas da igual: el sistema se
# usa desde tablets, donde el teclado capitaliza la primera letra solo.
AUTHENTICATION_BACKENDS = ['usuarios.backends.AutenticacionSinMayusculas']

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

# Django no trae un locale es-GT y el "es" genérico es el de España, que usa
# la coma para los decimales (Q 1.500,00). Guatemala usa el punto, así que se
# sobreescriben solo esos formatos. Ver config/formats/es/formats.py.
FORMAT_MODULE_PATH = ['config.formats']
USE_THOUSAND_SEPARATOR = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

if not DEBUG:
    # En desarrollo los estáticos los sirve el propio runserver; en producción
    # Django deja de hacerlo, así que entra WhiteNoise: los sirve desde el
    # mismo proceso, comprimidos y con un hash en el nombre para que al
    # actualizar el CSS los navegadores no se queden con la versión vieja.
    #
    # La alternativa sería montar un nginx aparte, que para 4–10 personas en
    # una red local es sumar una pieza más que puede fallar cuando no haya
    # nadie para arreglarla.
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
    STORAGES = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
    }

    # `manage.py check --deploy` levanta cuatro avisos que piden HTTPS. El
    # sistema corre por HTTP dentro de la red local de la empresa, sin
    # certificado, y activarlos rompería el acceso: una cookie marcada como
    # "secure" no viaja por HTTP, así que nadie podría iniciar sesión.
    #
    # Se silencian a propósito, no por descuido: así el chequeo sigue sirviendo
    # para detectar problemas nuevos en vez de quedar sepultado bajo avisos
    # que ya se revisaron. El día que se ponga HTTPS, se quitan de esta lista
    # y se activan SECURE_SSL_REDIRECT, SESSION_COOKIE_SECURE y
    # CSRF_COOKIE_SECURE.
    SILENCED_SYSTEM_CHECKS = [
        'security.W004',  # SECURE_HSTS_SECONDS
        'security.W008',  # SECURE_SSL_REDIRECT
        'security.W012',  # SESSION_COOKIE_SECURE
        'security.W016',  # CSRF_COOKIE_SECURE
    ]

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
