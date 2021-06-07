""" bookwyrm settings and configuration """
import os
from environs import Env

import requests
from django.utils.translation import gettext_lazy as _


env = Env()
DOMAIN = env("DOMAIN")
VERSION = "0.0.1"

PAGE_LENGTH = env("PAGE_LENGTH", 15)
DEFAULT_LANGUAGE = env("DEFAULT_LANGUAGE", "English")

# celery
CELERY_BROKER = "redis://:{}@redis_broker:{}/0".format(
    requests.utils.quote(env("REDIS_BROKER_PASSWORD", "")), env("REDIS_BROKER_PORT")
)
CELERY_RESULT_BACKEND = "redis://:{}@redis_broker:{}/0".format(
    requests.utils.quote(env("REDIS_BROKER_PASSWORD", "")), env("REDIS_BROKER_PORT")
)
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

# email
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env("EMAIL_PORT", 587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", False)
DEFAULT_FROM_EMAIL = "admin@{:s}".format(env("DOMAIN"))

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALE_PATHS = [
    os.path.join(BASE_DIR, "locale"),
]

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool("DEBUG", True)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", ["*"])

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django_rename_app",
    "bookwyrm",
    "celery",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "bookwyrm.timezone_middleware.TimezoneMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "bookwyrm.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": ["templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "bookwyrm.context_processors.site_settings",
            ],
        },
    },
]


WSGI_APPLICATION = "bookwyrm.wsgi.application"

# redis/activity streams settings
REDIS_ACTIVITY_HOST = env("REDIS_ACTIVITY_HOST", "localhost")
REDIS_ACTIVITY_PORT = env("REDIS_ACTIVITY_PORT", 6379)
REDIS_ACTIVITY_PASSWORD = env("REDIS_ACTIVITY_PASSWORD", None)

MAX_STREAM_LENGTH = int(env("MAX_STREAM_LENGTH", 200))
STREAMS = ["home", "local", "federated"]

# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": env("POSTGRES_DB", "fedireads"),
        "USER": env("POSTGRES_USER", "fedireads"),
        "PASSWORD": env("POSTGRES_PASSWORD", "fedireads"),
        "HOST": env("POSTGRES_HOST", ""),
        "PORT": env("POSTGRES_PORT", 5432),
    },
}


LOGIN_URL = "/login/"
AUTH_USER_MODEL = "bookwyrm.User"

# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

# pylint: disable=line-too-long
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = "en-us"
LANGUAGES = [
    ("en-us", _("English")),
    ("de-de", _("German")),
    ("es", _("Spanish")),
    ("fr-fr", _("French")),
    ("zh-hans", _("Simplified Chinese")),
]


TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, env("STATIC_ROOT", "static"))
MEDIA_URL = "/images/"
MEDIA_ROOT = os.path.join(BASE_DIR, env("MEDIA_ROOT", "images"))

USER_AGENT = "%s (BookWyrm/%s; +https://%s/)" % (
    requests.utils.default_user_agent(),
    VERSION,
    DOMAIN,
)
