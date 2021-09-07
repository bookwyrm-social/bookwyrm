""" background tasks """
import os
from celery import Celery

from celerywyrm import settings

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "celerywyrm.settings")
app = Celery(
    "tasks", broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_RESULT_BACKEND
)
