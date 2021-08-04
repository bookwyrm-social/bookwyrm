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

# Preview image
ENABLE_PREVIEW_IMAGES = env.bool("ENABLE_PREVIEW_IMAGES", False)
PREVIEW_BG_COLOR = env.str("PREVIEW_BG_COLOR", "use_dominant_color_light")
PREVIEW_TEXT_COLOR = env.str("PREVIEW_TEXT_COLOR", "#363636")
PREVIEW_IMG_WIDTH = env.int("PREVIEW_IMG_WIDTH", 1200)
PREVIEW_IMG_HEIGHT = env.int("PREVIEW_IMG_HEIGHT", 630)
PREVIEW_DEFAULT_COVER_COLOR = env.str("PREVIEW_DEFAULT_COVER_COLOR", "#002549")

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool("DEBUG", True)
USE_HTTPS = env.bool("USE_HTTPS", False)

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
    "storages",
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
    ("zh-hant", _("Traditional Chinese")),
]


TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True


USER_AGENT = "%s (BookWyrm/%s; +https://%s/)" % (
    requests.utils.default_user_agent(),
    VERSION,
    DOMAIN,
)


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Storage

PROTOCOL = "http"
if USE_HTTPS:
    PROTOCOL = "https"

USE_S3 = env.bool("USE_S3", False)

if USE_S3:
    # AWS settings
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_CUSTOM_DOMAIN = env("AWS_S3_CUSTOM_DOMAIN")
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", "")
    AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL")
    AWS_DEFAULT_ACL = "public-read"
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}
    # S3 Static settings
    STATIC_LOCATION = "static"
    STATIC_URL = "https://%s/%s/" % (AWS_S3_CUSTOM_DOMAIN, STATIC_LOCATION)
    STATICFILES_STORAGE = "bookwyrm.storage_backends.StaticStorage"
    # S3 Media settings
    MEDIA_LOCATION = "images"
    MEDIA_URL = "https://%s/%s/" % (AWS_S3_CUSTOM_DOMAIN, MEDIA_LOCATION)
    MEDIA_FULL_URL = MEDIA_URL
    DEFAULT_FILE_STORAGE = "bookwyrm.storage_backends.ImagesStorage"
    # I don't know if it's used, but the site crashes without it
    STATIC_ROOT = os.path.join(BASE_DIR, env("STATIC_ROOT", "static"))
    MEDIA_ROOT = os.path.join(BASE_DIR, env("MEDIA_ROOT", "images"))
else:
    STATIC_URL = "/static/"
    STATIC_ROOT = os.path.join(BASE_DIR, env("STATIC_ROOT", "static"))
    MEDIA_URL = "/images/"
    MEDIA_FULL_URL = "%s://%s%s" % (PROTOCOL, DOMAIN, MEDIA_URL)
    MEDIA_ROOT = os.path.join(BASE_DIR, env("MEDIA_ROOT", "images"))
