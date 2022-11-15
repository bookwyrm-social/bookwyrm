"""deactivate two factor auth"""

from django.core.management.base import BaseCommand, CommandError
from bookwyrm import models


class Command(BaseCommand):
    """command-line options"""

    help = "Remove Two Factor Authorisation from user"

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, **options):
        name = options["username"]
        user = models.User.objects.get(localname=name)
        user.two_factor_auth = False
        user.save(broadcast=False, update_fields=["two_factor_auth"])
        self.stdout.write(
            self.style.SUCCESS("Two Factor Authorisation was removed from user")
        )
