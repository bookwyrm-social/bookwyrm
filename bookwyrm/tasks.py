''' background tasks '''
import os
from celery import Celery

from bookwyrm import settings

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'celerywyrm.settings')
app = Celery(
    'tasks',
    broker=settings.CELERY_BROKER,
)
