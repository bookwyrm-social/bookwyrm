"""Delete user streams"""

from django.core.management.base import BaseCommand
import redis

from bookwyrm import settings

redis_instance = redis.from_url(settings.REDIS_ACTIVITY_URL)


def erase_streams():
    """throw the whole redis away"""
    redis_instance.flushall()


class Command(BaseCommand):
    """delete activity streams for all users"""

    help = "Delete all the user streams"

    def handle(self, *args, **options):
        """flush all, baby"""
        erase_streams()
