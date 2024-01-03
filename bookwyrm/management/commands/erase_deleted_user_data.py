""" Erase any data stored about deleted users """
import sys
from django.core.management.base import BaseCommand, CommandError
from bookwyrm import models
from bookwyrm.models.user import erase_user_data

# pylint: disable=missing-function-docstring
class Command(BaseCommand):
    """command-line options"""

    help = "Remove Two Factor Authorisation from user"

    def add_arguments(self, parser):  # pylint: disable=no-self-use
        parser.add_argument(
            "--dryrun",
            action="store_true",
            help="Preview users to be cleared without altering the database",
        )

    def handle(self, *args, **options):  # pylint: disable=unused-argument

        # Check for anything fishy
        bad_state = models.User.objects.filter(is_deleted=True, is_active=True)
        if bad_state.exists():
            raise CommandError(
                f"{bad_state.count()} user(s) marked as both active and deleted"
            )

        deleted_users = models.User.objects.filter(is_deleted=True)
        self.stdout.write(f"Found {deleted_users.count()} deleted users")
        if options["dryrun"]:
            self.stdout.write("\n".join(u.username for u in deleted_users[:5]))
            if deleted_users.count() > 5:
                self.stdout.write("... and more")
            sys.exit()

        self.stdout.write("Erasing user data:")
        for user_id in deleted_users.values_list("id", flat=True):
            erase_user_data.delay(user_id)
            self.stdout.write(".", ending="")

        self.stdout.write("")
        self.stdout.write("Tasks created successfully")
