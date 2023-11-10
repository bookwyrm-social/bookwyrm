""" background tasks """
import os
from celery import Celery

from celerywyrm import settings

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "celerywyrm.settings")
app = Celery(
    "tasks", broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_RESULT_BACKEND
)

# priorities - for backwards compatibility, will be removed next release
LOW = "low_priority"
MEDIUM = "medium_priority"
HIGH = "high_priority"

STREAMS = "streams"
IMAGES = "images"
SUGGESTED_USERS = "suggested_users"
EMAIL = "email"
CONNECTORS = "connectors"
LISTS = "lists"
INBOX = "inbox"
IMPORTS = "imports"
IMPORT_TRIGGERED = "import_triggered"
BROADCAST = "broadcast"
MISC = "misc"
