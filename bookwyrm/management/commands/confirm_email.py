""" manually confirm e-mail of user """
from django.core.management.base import BaseCommand

from bookwyrm import models


class Command(BaseCommand):
    """command-line options"""

    help = "Manually confirm email for user"

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, **options):
        name = options["username"]
        user = models.User.objects.get(localname=name)
        user.reactivate()
        self.stdout.write(self.style.SUCCESS("User's email is now confirmed."))
