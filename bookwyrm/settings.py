""" bookwyrm settings and configuration """
import os
from environs import Env

import requests
from django.utils.translation import gettext_lazy as _


env = Env()
env.read_env()
DOMAIN = env("DOMAIN")
VERSION = "0.0.1"

PAGE_LENGTH = env("PAGE_LENGTH", 15)
DEFAULT_LANGUAGE = env("DEFAULT_LANGUAGE", "English")

JS_CACHE = "c02929b1"

# email
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env("EMAIL_PORT", 587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", False)
DEFAULT_FROM_EMAIL = f"admin@{DOMAIN}"

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALE_PATHS = [
    os.path.join(BASE_DIR, "locale"),
]
LANGUAGE_COOKIE_NAME = env.str("LANGUAGE_COOKIE_NAME", "django_language")

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
    "imagekit",
    "storages",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "bookwyrm.middleware.TimezoneMiddleware",
    "bookwyrm.middleware.IPBlocklistMiddleware",
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

STREAMS = [
    {"key": "home", "name": _("Home Timeline"), "shortname": _("Home")},
    {"key": "books", "name": _("Books Timeline"), "shortname": _("Books")},
]

# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": env("POSTGRES_DB", "fedireads"),
        "USER": env("POSTGRES_USER", "fedireads"),
        "PASSWORD": env("POSTGRES_PASSWORD", "fedireads"),
        "HOST": env("POSTGRES_HOST", ""),
        "PORT": env("PGPORT", 5432),
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
    ("de-de", _("Deutsch (German)")),  # German
    ("es", _("Español (Spanish)")),  # Spanish
    ("fr-fr", _("Français (French)")),  # French
    ("zh-hans", _("简体中文 (Simplified Chinese)")),  # Simplified Chinese
    ("zh-hant", _("繁體中文 (Traditional Chinese)")),  # Traditional Chinese
]


TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True


agent = requests.utils.default_user_agent()
USER_AGENT = f"{agent} (BookWyrm/{VERSION}; +https://{DOMAIN}/)"

# Imagekit generated thumbnails
ENABLE_THUMBNAIL_GENERATION = env.bool("ENABLE_THUMBNAIL_GENERATION", False)
IMAGEKIT_CACHEFILE_DIR = "thumbnails"

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
    STATIC_URL = f"{PROTOCOL}://{AWS_S3_CUSTOM_DOMAIN}/{STATIC_LOCATION}/"
    STATICFILES_STORAGE = "bookwyrm.storage_backends.StaticStorage"
    # S3 Media settings
    MEDIA_LOCATION = "images"
    MEDIA_URL = f"{PROTOCOL}://{AWS_S3_CUSTOM_DOMAIN}/{MEDIA_LOCATION}/"
    MEDIA_FULL_URL = MEDIA_URL
    STATIC_FULL_URL = STATIC_URL
    DEFAULT_FILE_STORAGE = "bookwyrm.storage_backends.ImagesStorage"
    # I don't know if it's used, but the site crashes without it
    STATIC_ROOT = os.path.join(BASE_DIR, env("STATIC_ROOT", "static"))
    MEDIA_ROOT = os.path.join(BASE_DIR, env("MEDIA_ROOT", "images"))
else:
    STATIC_URL = "/static/"
    STATIC_ROOT = os.path.join(BASE_DIR, env("STATIC_ROOT", "static"))
    MEDIA_URL = "/images/"
    MEDIA_FULL_URL = f"{PROTOCOL}://{DOMAIN}{MEDIA_URL}"
    STATIC_FULL_URL = f"{PROTOCOL}://{DOMAIN}{STATIC_URL}"
    MEDIA_ROOT = os.path.join(BASE_DIR, env("MEDIA_ROOT", "images"))
