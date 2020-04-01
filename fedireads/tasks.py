''' background tasks '''
from celery import Celery
import os

from fedireads import settings

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fr_celery.settings')
app = Celery(
    'tasks',
    broker=settings.CELERY_BROKER,
)


