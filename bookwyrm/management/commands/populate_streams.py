""" Re-create user streams """
from django.core.management.base import BaseCommand
from bookwyrm import activitystreams, lists_stream, models


def populate_streams(stream=None):
    """build all the streams for all the users"""
    streams = [stream] if stream else activitystreams.streams.keys()
    print("Populating streams", streams)
    users = models.User.objects.filter(
        local=True,
        is_active=True,
    ).order_by("-last_active_date")
    print("This may take a long time! Please be patient.")
    for user in users:
        print(".", end="")
        lists_stream.populate_lists_task.delay(user.id)
        for stream_key in streams:
            print(".", end="")
            activitystreams.populate_stream_task.delay(stream_key, user.id)


class Command(BaseCommand):
    """start all over with user streams"""

    help = "Populate streams for all users"

    def add_arguments(self, parser):
        parser.add_argument(
            "--stream",
            default=None,
            help="Specifies which time of stream to populate",
        )

    # pylint: disable=no-self-use,unused-argument
    def handle(self, *args, **options):
        """run feed builder"""
        stream = options.get("stream")
        populate_streams(stream=stream)
