"""Permanently delete local users who never confirmed their email."""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from bookwyrm import models


def stale_accounts(days):
    """Local accounts still waiting on email confirmation."""
    cutoff = timezone.now() - timedelta(days=max(days, 0))
    return models.User.objects.filter(
        local=True,
        is_active=False,
        is_deleted=False,
        is_superuser=False,
        deactivation_reason="pending",
        created_date__lte=cutoff,
    ).order_by("created_date", "id")


def account_row(user, now=None):
    """One preview line: username - email - age."""
    now = now or timezone.now()
    age_days = max((now - user.created_date).days, 0)
    unit = "day" if age_days == 1 else "days"
    name = user.localname or user.username
    return f"{name} - {user.email} - {age_days} {unit} ago"


def permanently_delete_user(user):
    """Remove the user row. User.delete() only deactivates the account."""
    key_pair_id = user.key_pair_id
    with transaction.atomic():
        # Default shelves reference the user with PROTECT, so they have to go
        # before the user row. Queryset delete skips the soft-delete override.
        models.ShelfBook.objects.filter(user=user).delete()
        models.Shelf.objects.filter(user=user).delete()
        models.User.objects.filter(pk=user.pk).delete()
        if key_pair_id:
            models.KeyPair.objects.filter(pk=key_pair_id).delete()


class Command(BaseCommand):
    """command-line options"""

    help = "Permanently delete local users who never confirmed their email"

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Delete matching accounts without prompting",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=0,
            help=(
                "Only delete accounts registered at least this many days ago. "
                "The default is 0, which includes every unconfirmed account."
            ),
        )

    def handle(self, *args, **options):
        days = options.get("days") or 0
        accounts = list(stale_accounts(days))
        if not accounts:
            self.stdout.write("No unconfirmed accounts to clean up.")
            return

        now = timezone.now()
        self.stdout.write("This run would clean the following accounts:")
        self.stdout.write("Username - Email - Registration date")
        self.stdout.write("")
        for user in accounts:
            self.stdout.write(account_row(user, now=now))
        self.stdout.write("")
        self.stdout.write(
            "Permanently delete those unconfirmed users? This action cannot be undone!"
        )

        if not options.get("yes") and not self.confirmed():
            self.stdout.write("No accounts were deleted.")
            return

        deleted = 0
        for user in accounts:
            name = user.localname or user.username
            try:
                permanently_delete_user(user)
            except ProtectedError:
                self.stdout.write(
                    f"Skipped {name}: account still has data that blocks deletion."
                )
                continue
            deleted += 1

        label = "account" if deleted == 1 else "accounts"
        self.stdout.write(f"Deleted {deleted} unconfirmed {label}.")

    def confirmed(self):
        """Prompt y/N. Anything other than yes leaves the database alone."""
        try:
            answer = input("y/N ")
        except EOFError:
            return False
        return answer.strip().lower() in {"y", "yes"}
