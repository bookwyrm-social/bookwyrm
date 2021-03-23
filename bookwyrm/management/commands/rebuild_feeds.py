""" Delete and re-create user feeds """
from django.core.management.base import BaseCommand
import redis

from bookwyrm import activitystreams, models, settings

r = redis.Redis(
    host=settings.REDIS_ACTIVITY_HOST, port=settings.REDIS_ACTIVITY_PORT, db=0
)

def erase_feeds():
    """ throw the whole redis away """
    r.flushall()

def create_feeds():
    """ build all the fields for all the users """
    users = models.User.objects.filter(
        local=True,
        is_active=True,
    )
    for user in users:
        for stream in activitystreams.streams.values():
            stream.populate_stream(user)


class Command(BaseCommand):
    """ start all over with user feeds """

    help = "Delete and re-create all the user feeds"
    # pylint: disable=no-self-use,unused-argument
    def handle(self, *args, **options):
        """ run feed builder """
        erase_feeds()
        create_feeds()
