""" bookwyrm settings and configuration """
# pylint: disable=wildcard-import
# pylint: disable=unused-wildcard-import
from bookwyrm.settings import *

# pylint: disable=line-too-long
REDIS_BROKER_PASSWORD = requests.utils.quote(env("REDIS_BROKER_PASSWORD", ""))
REDIS_BROKER_HOST = env("REDIS_BROKER_HOST", "redis_broker")
REDIS_BROKER_PORT = env("REDIS_BROKER_PORT", 6379)
REDIS_BROKER_DB_INDEX = env("REDIS_BROKER_DB_INDEX", 0)
REDIS_BROKER_URL = env(
    "REDIS_BROKER_URL",
    f"redis://:{REDIS_BROKER_PASSWORD}@{REDIS_BROKER_HOST}:{REDIS_BROKER_PORT}/{REDIS_BROKER_DB_INDEX}",
)

CELERY_BROKER_URL = REDIS_BROKER_URL.replace("unix:", "redis+socket:")
CELERY_RESULT_BACKEND = REDIS_BROKER_URL.replace("unix:", "redis+socket:")

CELERY_DEFAULT_QUEUE = "low_priority"
CELERY_CREATE_MISSING_QUEUES = True

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TIMEZONE = env("TIME_ZONE", "UTC")

FLOWER_PORT = env("FLOWER_PORT")

INSTALLED_APPS = INSTALLED_APPS + [
    "celerywyrm",
]

ROOT_URLCONF = "celerywyrm.urls"

WSGI_APPLICATION = "celerywyrm.wsgi.application"
