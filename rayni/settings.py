import os, environ
from pathlib import Path

BASE_DIR=Path(__file__).resolve().parent.parent
env=environ.Env(DEBUG=(bool, True))
if os.path.exists(BASE_DIR/'.env'):
    environ.Env.read_env(BASE_DIR/'.env')

SECRET_KEY=env("SECRET_KEY", default="dev-secret")
DEBUG=env.bool("DEBUG", default=True)
ALLOWED_HOSTS=["*"]

INSTALLED_APPS=[
 "django.contrib.admin","django.contrib.auth","django.contrib.contenttypes","django.contrib.sessions","django.contrib.messages","django.contrib.staticfiles",
 "rest_framework","drf_spectacular","django_filters","corsheaders","django.contrib.postgres",
 "core",
]
MIDDLEWARE=[
 "corsheaders.middleware.CorsMiddleware",
 "django.middleware.security.SecurityMiddleware",
 "django.contrib.sessions.middleware.SessionMiddleware",
 "django.middleware.common.CommonMiddleware",
 "django.middleware.csrf.CsrfViewMiddleware",
 "django.contrib.auth.middleware.AuthenticationMiddleware",
 "django.contrib.messages.middleware.MessageMiddleware",
]
ROOT_URLCONF="rayni.urls"
TEMPLATES=[{
 "BACKEND":"django.template.backends.django.DjangoTemplates",
 "DIRS":[],
 "APP_DIRS":True,
 "OPTIONS":{"context_processors":["django.template.context_processors.debug","django.template.context_processors.request","django.contrib.auth.context_processors.auth","django.contrib.messages.context_processors.messages"]}
}]
WSGI_APPLICATION="rayni.wsgi.application"

DATABASES={
 "default": env.db_url("DATABASE_URL", default="postgres://rayni:rayni@db:5432/rayni")
}

LANGUAGE_CODE="en-us"; TIME_ZONE="UTC"; USE_I18N=True; USE_TZ=True
STATIC_URL="/static/"
DEFAULT_AUTO_FIELD="django.db.models.BigAutoField"
CORS_ALLOW_ALL_ORIGINS=True

REST_FRAMEWORK={
 "DEFAULT_SCHEMA_CLASS":"drf_spectacular.openapi.AutoSchema",
 "DEFAULT_PERMISSION_CLASSES":["rest_framework.permissions.AllowAny"],
 "DEFAULT_FILTER_BACKENDS":["django_filters.rest_framework.DjangoFilterBackend"]
}
SPECTACULAR_SETTINGS={"TITLE":"Rayni API","VERSION":"1.0.0"}

OPENAI_API_KEY=env("OPENAI_API_KEY", default=None)

CELERY_BROKER_URL=env("CELERY_BROKER_URL", default="redis://redis:6379/0")
CELERY_RESULT_BACKEND=CELERY_BROKER_URL
