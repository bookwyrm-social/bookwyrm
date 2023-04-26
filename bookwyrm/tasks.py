""" background tasks """
import os
from celery import Celery

from celerywyrm import settings

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "celerywyrm.settings")
app = Celery(
    "tasks", broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_RESULT_BACKEND
)

# priorities
LOW = "low_priority"
MEDIUM = "medium_priority"
HIGH = "high_priority"
# import items get their own queue because they're such a pain in the ass
IMPORTS = "imports"
# I keep making more queues?? this one broadcasting out
BROADCAST = "broadcast"
