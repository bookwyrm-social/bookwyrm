""" Delete user streams """
from django.core.management.base import BaseCommand
import redis

from bookwyrm import settings

r = redis.from_url(settings.REDIS_ACTIVITY_URL)


def erase_streams():
    """throw the whole redis away"""
    r.flushall()


class Command(BaseCommand):
    """delete activity streams for all users"""

    help = "Delete all the user streams"
    # pylint: disable=no-self-use,unused-argument
    def handle(self, *args, **options):
        """flush all, baby"""
        erase_streams()
