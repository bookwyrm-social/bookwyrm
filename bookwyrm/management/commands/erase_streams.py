""" Delete user streams """
from django.core.management.base import BaseCommand
import redis

from bookwyrm import settings

r = redis.from_url(f"{settings.REDIS_ACTIVITY_HOST}?db={settings.REDIS_ACTIVITY_DB_INDEX}") if settings.REDIS_ACTIVITY_HOST.startswith("unix://") else redis.Redis(
    host=settings.REDIS_ACTIVITY_HOST,
    port=settings.REDIS_ACTIVITY_PORT,
    password=settings.REDIS_ACTIVITY_PASSWORD,
    db=settings.REDIS_ACTIVITY_DB_INDEX,
)


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
