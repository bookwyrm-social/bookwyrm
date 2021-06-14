""" Re-create user streams """
from django.core.management.base import BaseCommand
import redis

from bookwyrm import activitystreams, models, settings

r = redis.Redis(
    host=settings.REDIS_ACTIVITY_HOST, port=settings.REDIS_ACTIVITY_PORT, db=0
)


def populate_streams():
    """build all the streams for all the users"""
    users = models.User.objects.filter(
        local=True,
        is_active=True,
    )
    for user in users:
        for stream in activitystreams.streams.values():
            stream.populate_streams(user)


class Command(BaseCommand):
    """start all over with user streams"""

    help = "Populate streams for all users"
    # pylint: disable=no-self-use,unused-argument
    def handle(self, *args, **options):
        """run feed builder"""
        populate_streams()
