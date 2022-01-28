""" Re-create list streams """
from django.core.management.base import BaseCommand
from bookwyrm import lists_stream, models


def populate_lists_streams():
    """build all the lists streams for all the users"""
    print("Populating lists streams")
    users = models.User.objects.filter(
        local=True,
        is_active=True,
    ).order_by("-last_active_date")
    print("This may take a long time! Please be patient.")
    for user in users:
        print(".", end="")
        lists_stream.populate_lists_task.delay(user.id)
    print("\nAll done, thank you for your patience!")


class Command(BaseCommand):
    """start all over with lists streams"""

    help = "Populate list streams for all users"

    # pylint: disable=no-self-use,unused-argument
    def handle(self, *args, **options):
        """run feed builder"""
        populate_lists_streams()
