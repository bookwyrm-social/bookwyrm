""" bookwyrm settings and configuration """
import os
from environs import Env

import requests
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ImproperlyConfigured


# pylint: disable=line-too-long

env = Env()
env.read_env()
DOMAIN = env("DOMAIN")
VERSION = "0.6.4"

RELEASE_API = env(
    "RELEASE_API",
    "https://api.github.com/repos/bookwyrm-social/bookwyrm/releases/latest",
)

PAGE_LENGTH = env.int("PAGE_LENGTH", 15)
DEFAULT_LANGUAGE = env("DEFAULT_LANGUAGE", "English")

JS_CACHE = "b972a43c"

# email
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env.int("EMAIL_PORT", 587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", False)
EMAIL_SENDER_NAME = env("EMAIL_SENDER_NAME", "admin")
EMAIL_SENDER_DOMAIN = env("EMAIL_SENDER_DOMAIN", DOMAIN)
EMAIL_SENDER = f"{EMAIL_SENDER_NAME}@{EMAIL_SENDER_DOMAIN}"

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALE_PATHS = [
    os.path.join(BASE_DIR, "locale"),
]
LANGUAGE_COOKIE_NAME = env.str("LANGUAGE_COOKIE_NAME", "django_language")

STATIC_ROOT = os.path.join(BASE_DIR, env("STATIC_ROOT", "static"))
MEDIA_ROOT = os.path.join(BASE_DIR, env("MEDIA_ROOT", "images"))

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Preview image
ENABLE_PREVIEW_IMAGES = env.bool("ENABLE_PREVIEW_IMAGES", False)
PREVIEW_BG_COLOR = env.str("PREVIEW_BG_COLOR", "use_dominant_color_light")
PREVIEW_TEXT_COLOR = env.str("PREVIEW_TEXT_COLOR", "#363636")
PREVIEW_IMG_WIDTH = env.int("PREVIEW_IMG_WIDTH", 1200)
PREVIEW_IMG_HEIGHT = env.int("PREVIEW_IMG_HEIGHT", 630)
PREVIEW_DEFAULT_COVER_COLOR = env.str("PREVIEW_DEFAULT_COVER_COLOR", "#002549")
PREVIEW_DEFAULT_FONT = env.str("PREVIEW_DEFAULT_FONT", "Source Han Sans")

FONTS = {
    "Source Han Sans": {
        "directory": "source_han_sans",
        "filename": "SourceHanSans-VF.ttf.ttc",
        "url": "https://github.com/adobe-fonts/source-han-sans/raw/release/Variable/OTC/SourceHanSans-VF.ttf.ttc",
    }
}
FONT_DIR = os.path.join(STATIC_ROOT, "fonts")

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool("DEBUG", True)
USE_HTTPS = env.bool("USE_HTTPS", not DEBUG)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY")
if not DEBUG and SECRET_KEY == "7(2w1sedok=aznpq)ta1mc4i%4h=xx@hxwx*o57ctsuml0x%fr":
    raise ImproperlyConfigured("You must change the SECRET_KEY env variable")

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
    "sass_processor",
    "bookwyrm",
    "celery",
    "django_celery_beat",
    "imagekit",
    "storages",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "csp.middleware.CSPMiddleware",
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

LOG_LEVEL = env("LOG_LEVEL", "INFO").upper()
# Override aspects of the default handler to our taste
# See https://docs.djangoproject.com/en/3.2/topics/logging/#default-logging-configuration
# for a reference to the defaults we're overriding
#
# It seems that in order to override anything you have to include its
# entire dependency tree (handlers and filters) which makes this a
# bit verbose
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        # These are copied from the default configuration, required for
        # implementing mail_admins below
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
        "ignore_missing_variable": {
            "()": "bookwyrm.utils.log.IgnoreVariableDoesNotExist",
        },
    },
    "handlers": {
        # Overrides the default handler to make it log to console
        # regardless of the DEBUG setting (default is to not log to
        # console if DEBUG=False)
        "console": {
            "level": LOG_LEVEL,
            "filters": ["ignore_missing_variable"],
            "class": "logging.StreamHandler",
        },
        # This is copied as-is from the default logger, and is
        # required for the django section below
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
        },
    },
    "loggers": {
        # Install our new console handler for Django's logger, and
        # override the log level while we're at it
        "django": {
            "handlers": ["console", "mail_admins"],
            "level": LOG_LEVEL,
        },
        "django.utils.autoreload": {
            "level": "INFO",
        },
        # Add a bookwyrm-specific logger
        "bookwyrm": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
        },
    },
}

STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "sass_processor.finders.CssFinder",
]

SASS_PROCESSOR_INCLUDE_FILE_PATTERN = r"^.+\.[s]{0,1}(?:a|c)ss$"
# when debug is disabled, make sure to compile themes once with `./bw-dev compile_themes`
SASS_PROCESSOR_ENABLED = DEBUG

# minify css is production but not dev
if not DEBUG:
    SASS_OUTPUT_STYLE = "compressed"

WSGI_APPLICATION = "bookwyrm.wsgi.application"

# redis/activity streams settings
REDIS_ACTIVITY_HOST = env("REDIS_ACTIVITY_HOST", "localhost")
REDIS_ACTIVITY_PORT = env.int("REDIS_ACTIVITY_PORT", 6379)
REDIS_ACTIVITY_PASSWORD = requests.utils.quote(env("REDIS_ACTIVITY_PASSWORD", ""))
REDIS_ACTIVITY_DB_INDEX = env.int("REDIS_ACTIVITY_DB_INDEX", 0)
REDIS_ACTIVITY_URL = env(
    "REDIS_ACTIVITY_URL",
    f"redis://:{REDIS_ACTIVITY_PASSWORD}@{REDIS_ACTIVITY_HOST}:{REDIS_ACTIVITY_PORT}/{REDIS_ACTIVITY_DB_INDEX}",
)
MAX_STREAM_LENGTH = env.int("MAX_STREAM_LENGTH", 200)

STREAMS = [
    {"key": "home", "name": _("Home Timeline"), "shortname": _("Home")},
    {"key": "books", "name": _("Books Timeline"), "shortname": _("Books")},
]

# Search configuration
# total time in seconds that the instance will spend searching connectors
SEARCH_TIMEOUT = env.int("SEARCH_TIMEOUT", 8)
# timeout for a query to an individual connector
QUERY_TIMEOUT = env.int("INTERACTIVE_QUERY_TIMEOUT", env.int("QUERY_TIMEOUT", 5))

# Redis cache backend
if env.bool("USE_DUMMY_CACHE", False):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_ACTIVITY_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
        }
    }

    SESSION_ENGINE = "django.contrib.sessions.backends.cache"
    SESSION_CACHE_ALIAS = "default"

# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": env("POSTGRES_DB", "bookwyrm"),
        "USER": env("POSTGRES_USER", "bookwyrm"),
        "PASSWORD": env("POSTGRES_PASSWORD", "bookwyrm"),
        "HOST": env("POSTGRES_HOST", ""),
        "PORT": env.int("PGPORT", 5432),
    },
}


LOGIN_URL = "/login/"
AUTH_USER_MODEL = "bookwyrm.User"

# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

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

LANGUAGE_CODE = env("LANGUAGE_CODE", "en-us")
LANGUAGES = [
    ("en-us", _("English")),
    ("ca-es", _("Català (Catalan)")),
    ("de-de", _("Deutsch (German)")),
    ("eo-uy", _("Esperanto (Esperanto)")),
    ("es-es", _("Español (Spanish)")),
    ("eu-es", _("Euskara (Basque)")),
    ("gl-es", _("Galego (Galician)")),
    ("it-it", _("Italiano (Italian)")),
    ("fi-fi", _("Suomi (Finnish)")),
    ("fr-fr", _("Français (French)")),
    ("lt-lt", _("Lietuvių (Lithuanian)")),
    ("no-no", _("Norsk (Norwegian)")),
    ("pl-pl", _("Polski (Polish)")),
    ("pt-br", _("Português do Brasil (Brazilian Portuguese)")),
    ("pt-pt", _("Português Europeu (European Portuguese)")),
    ("ro-ro", _("Română (Romanian)")),
    ("sv-se", _("Svenska (Swedish)")),
    ("zh-hans", _("简体中文 (Simplified Chinese)")),
    ("zh-hant", _("繁體中文 (Traditional Chinese)")),
]

LANGUAGE_ARTICLES = {
    "English": {"the", "a", "an"},
}

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True


agent = requests.utils.default_user_agent()
USER_AGENT = f"{agent} (BookWyrm/{VERSION}; +https://{DOMAIN}/)"

# Imagekit generated thumbnails
ENABLE_THUMBNAIL_GENERATION = env.bool("ENABLE_THUMBNAIL_GENERATION", False)
IMAGEKIT_CACHEFILE_DIR = "thumbnails"
IMAGEKIT_DEFAULT_CACHEFILE_STRATEGY = "bookwyrm.thumbnail_generation.Strategy"

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CSP_ADDITIONAL_HOSTS = env.list("CSP_ADDITIONAL_HOSTS", [])

# Storage

PROTOCOL = "http"
if USE_HTTPS:
    PROTOCOL = "https"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

USE_S3 = env.bool("USE_S3", False)
USE_AZURE = env.bool("USE_AZURE", False)

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
    CSP_DEFAULT_SRC = ["'self'", AWS_S3_CUSTOM_DOMAIN] + CSP_ADDITIONAL_HOSTS
    CSP_SCRIPT_SRC = ["'self'", AWS_S3_CUSTOM_DOMAIN] + CSP_ADDITIONAL_HOSTS
elif USE_AZURE:
    AZURE_ACCOUNT_NAME = env("AZURE_ACCOUNT_NAME")
    AZURE_ACCOUNT_KEY = env("AZURE_ACCOUNT_KEY")
    AZURE_CONTAINER = env("AZURE_CONTAINER")
    AZURE_CUSTOM_DOMAIN = env("AZURE_CUSTOM_DOMAIN")
    # Azure Static settings
    STATIC_LOCATION = "static"
    STATIC_URL = (
        f"{PROTOCOL}://{AZURE_CUSTOM_DOMAIN}/{AZURE_CONTAINER}/{STATIC_LOCATION}/"
    )
    STATICFILES_STORAGE = "bookwyrm.storage_backends.AzureStaticStorage"
    # Azure Media settings
    MEDIA_LOCATION = "images"
    MEDIA_URL = (
        f"{PROTOCOL}://{AZURE_CUSTOM_DOMAIN}/{AZURE_CONTAINER}/{MEDIA_LOCATION}/"
    )
    MEDIA_FULL_URL = MEDIA_URL
    STATIC_FULL_URL = STATIC_URL
    DEFAULT_FILE_STORAGE = "bookwyrm.storage_backends.AzureImagesStorage"
    CSP_DEFAULT_SRC = ["'self'", AZURE_CUSTOM_DOMAIN] + CSP_ADDITIONAL_HOSTS
    CSP_SCRIPT_SRC = ["'self'", AZURE_CUSTOM_DOMAIN] + CSP_ADDITIONAL_HOSTS
else:
    STATIC_URL = "/static/"
    MEDIA_URL = "/images/"
    MEDIA_FULL_URL = f"{PROTOCOL}://{DOMAIN}{MEDIA_URL}"
    STATIC_FULL_URL = f"{PROTOCOL}://{DOMAIN}{STATIC_URL}"
    CSP_DEFAULT_SRC = ["'self'"] + CSP_ADDITIONAL_HOSTS
    CSP_SCRIPT_SRC = ["'self'"] + CSP_ADDITIONAL_HOSTS

CSP_INCLUDE_NONCE_IN = ["script-src"]

OTEL_EXPORTER_OTLP_ENDPOINT = env("OTEL_EXPORTER_OTLP_ENDPOINT", None)
OTEL_EXPORTER_OTLP_HEADERS = env("OTEL_EXPORTER_OTLP_HEADERS", None)
OTEL_SERVICE_NAME = env("OTEL_SERVICE_NAME", None)
OTEL_EXPORTER_CONSOLE = env.bool("OTEL_EXPORTER_CONSOLE", False)

TWO_FACTOR_LOGIN_MAX_SECONDS = env.int("TWO_FACTOR_LOGIN_MAX_SECONDS", 60)
TWO_FACTOR_LOGIN_VALIDITY_WINDOW = env.int("TWO_FACTOR_LOGIN_VALIDITY_WINDOW", 2)

HTTP_X_FORWARDED_PROTO = env.bool("SECURE_PROXY_SSL_HEADER", False)
if HTTP_X_FORWARDED_PROTO:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Instance Actor for signing GET requests to "secure mode"
# Mastodon servers.
# Do not change this setting unless you already have an existing
# user with the same username - in which case you should change it!
INSTANCE_ACTOR_USERNAME = "bookwyrm.instance.actor"
