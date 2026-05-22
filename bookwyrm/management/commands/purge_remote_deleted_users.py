"""Remove remove delted users from the database"""

from django.core.management.base import BaseCommand
from django.db.models import Count, F
from bookwyrm import models


class Command(BaseCommand):
    """command-line options"""

    help = "Remove users that were only added because they were deleted"

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Delete identified users from database",
        )

    def handle(self, *args, **options):
        """Find and report on user accounts that can be purged"""

        targets = models.User.objects.filter(
            local=False,
            is_deleted=True,
            is_active=False,
            bookwyrm_user=False,
            status=None,
            favorites=None,
        ).filter(date_joined__date=F("last_active_date__date"))

        target_ids = targets.values_list("id", flat=True)

        statuses = models.Status.objects.filter(user__in=target_ids)
        followers = models.User.objects.filter(local=True, followers__in=target_ids)
        followed = models.User.objects.filter(local=True, following__in=target_ids)
        favorites = models.Favorite.objects.filter(user__in=target_ids)

        servers = (
            models.FederatedServer.objects.filter(user__in=target_ids)
            .annotate(total_users=Count("user"))
            .order_by("-total_users")
        )

        if options["confirm"]:
            """This time for real"""

            try:
                self.stdout.write(
                    f"\nPurging {targets.count()} users from {servers.count()} instances:\n\n"
                )
                server_list = [(s.server_name, s.total_users) for s in servers.all()]
                for name, total in server_list:
                    self.stdout.write(f"{name}: {total}")
                self.stdout.write("\nDeleting...")

                # this is a bulk operation so it bypasses the overridden method and actually deletes
                # see https://docs.djangoproject.com/en/5.2/topics/db/queries/#topics-db-queries-delete
                targets.delete()

                self.stdout.write("User deletion completed.")
                self.stdout.write(
                    "Thankyou for being a BookWyrm administrator, happy reading!\n\n"
                )

            except Exception as e:
                self.stdout.write(f"User deletion failed with error:\n\n{e}")

        else:
            self.stdout.write(
                f"\nYour database has {targets.count()} candidates for deletion from {servers.count()} instances.\n"
            )
            self.stdout.write("Values associated with these users:\n\n")
            self.stdout.write("------------------------------------------------")
            self.stdout.write(f"Statuses:         {statuses.count()}")
            self.stdout.write(f"Favorites:        {favorites.count()}")
            self.stdout.write(f"Local followers:  {followers.count()}")
            self.stdout.write(f"Locals following: {followed.count()}")
            self.stdout.write("------------------------------------------------\n\n")
            associated_models_count = (
                statuses.count()
                + followers.count()
                + followed.count()
                + favorites.count()
            )

            if associated_models_count == 0:
                self.stdout.write("It is safe to delete these users.")
                self.stdout.write(
                    "To do so, run the command again with the --confirm flag\n\n"
                )
            else:
                self.stdout.write("It is NOT SAFE to delete all these users.")
                self.stdout.write(
                    "Please log an issue at https://github.com/bookwyrm-social/bookwyrm/issues with this output\n\n"
                )
