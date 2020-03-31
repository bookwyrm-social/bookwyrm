''' background tasks '''
from celery import Celery
import os

from fedireads import models
from fedireads import status as status_builder
from fedireads.outgoing import get_or_create_remote_user
from fedireads import settings

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fr_celery.settings')
app = Celery(
    'tasks',
    broker=settings.CELERY_BROKER,
)


@app.task
def handle_incoming_favorite(activity):
    ''' ugh '''
    print('here we go')
    try:
        status_id = activity['object'].split('/')[-1]
        print(status_id)
        status = models.Status.objects.get(id=status_id)
        liker = get_or_create_remote_user(activity['actor'])
    except (models.Status.DoesNotExist, models.User.DoesNotExist):
        print('gonna return')
        return

    print('got the status okay')
    if not liker.local:
        status_builder.create_favorite_from_activity(liker, activity)

    status_builder.create_notification(
        status.user,
        'FAVORITE',
        related_user=liker,
        related_status=status,
    )
    print('done')

