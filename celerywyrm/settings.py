""" bookwyrm settings and configuration """
# pylint: disable=wildcard-import
# pylint: disable=unused-wildcard-import
from bookwyrm.settings import *
from celery.schedules import crontab

QUERY_TIMEOUT = env.int("CELERY_QUERY_TIMEOUT", env.int("QUERY_TIMEOUT", 30))

# pylint: disable=line-too-long
REDIS_BROKER_PASSWORD = requests.compat.quote(env("REDIS_BROKER_PASSWORD", ""))
REDIS_BROKER_HOST = env("REDIS_BROKER_HOST", "redis_broker")
REDIS_BROKER_PORT = env.int("REDIS_BROKER_PORT", 6379)
REDIS_BROKER_DB_INDEX = env.int("REDIS_BROKER_DB_INDEX", 0)
REDIS_BROKER_URL = env(
    "REDIS_BROKER_URL",
    f"redis://:{REDIS_BROKER_PASSWORD}@{REDIS_BROKER_HOST}:{REDIS_BROKER_PORT}/{REDIS_BROKER_DB_INDEX}",
)

CELERY_BROKER_URL = env(
    "CELERY_BROKER_URL", REDIS_BROKER_URL.replace("unix:", "redis+socket:")
)
CELERY_RESULT_BACKEND = env(
    "CELERY_RESULT_BACKEND", REDIS_BROKER_URL.replace("unix:", "redis+socket:")
)

CELERY_DEFAULT_QUEUE = "low_priority"
CELERY_CREATE_MISSING_QUEUES = True

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TIMEZONE = env("TIME_ZONE", "UTC")

# Beat schedule for periodic tasks
CELERY_BEAT_SCHEDULE = {
    "cleanup-backoff-entries": {
        "task": "bookwyrm.tasks.cleanup_backoff_entries",
        "schedule": crontab(hour=0, minute=0),  # Daily at midnight
    },
    "sync-connector-health": {
        "task": "bookwyrm.connectors.connector_backoff.sync_connector_health",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
    "send-daily-newsletter": {
        "task": "bookwyrm.newsletter.send_daily_newsletter",
        "schedule": crontab(hour=5, minute=0),  # Daily at 5 AM UTC (7-8 AM Lithuanian time)
    },
}

CELERY_WORKER_CONCURRENCY = env("CELERY_WORKER_CONCURRENCY", None)
CELERY_TASK_SOFT_TIME_LIMIT = env("CELERY_TASK_SOFT_TIME_LIMIT", None)

FLOWER_PORT = env.int("FLOWER_PORT", 8888)

INSTALLED_APPS = INSTALLED_APPS + [
    "celerywyrm",
]

# Use bookwyrm.urls so email templates can resolve URL names like 'prefs-profile'
ROOT_URLCONF = "bookwyrm.urls"

WSGI_APPLICATION = "celerywyrm.wsgi.application"
