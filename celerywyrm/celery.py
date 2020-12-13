''' configures celery for task management '''
from __future__ import absolute_import, unicode_literals
import os

from celery import Celery
from . import settings


# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'celerywyrm.settings')

app = Celery('celerywyrm')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
app.autodiscover_tasks(['bookwyrm'], related_name='activitypub.base_activity')
app.autodiscover_tasks(['bookwyrm'], related_name='books_manager')
app.autodiscover_tasks(['bookwyrm'], related_name='broadcast')
app.autodiscover_tasks(['bookwyrm'], related_name='emailing')
app.autodiscover_tasks(['bookwyrm'], related_name='goodreads_import')
app.autodiscover_tasks(['bookwyrm'], related_name='incoming')
app.autodiscover_tasks(['bookwyrm'], related_name='models.user')
