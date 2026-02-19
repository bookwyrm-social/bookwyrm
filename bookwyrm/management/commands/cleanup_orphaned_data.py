"""Management command to clean up orphaned data.

Provides safe cleanup of orphaned records and invalid data.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q, F

from bookwyrm import models


class Command(BaseCommand):
    """Clean up orphaned data from deleted users and books."""

    help = "Clean up orphaned data safely"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )
        parser.add_argument(
            "--cleanup",
            type=str,
            nargs="+",
            choices=[
                "statuses",
                "reviews",
                "shelf-books",
                "list-items",
                "notifications",
                "relationships",
                "all",
            ],
            default=["all"],
            help="Types of cleanup to perform",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Batch size for deletions (default: 1000)",
        )

    def handle(self, *args, **options):
        """Execute the cleanup command."""
        dry_run = options["dry_run"]
        cleanups = options["cleanup"]
        batch_size = options["batch_size"]

        if "all" in cleanups:
            cleanups = [
                "statuses",
                "reviews",
                "shelf-books",
                "list-items",
                "notifications",
                "relationships",
            ]

        self.stdout.write("=" * 80)
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "BookWyrm Data Cleanup" + (" (DRY RUN)" if dry_run else "")
            )
        )
        self.stdout.write("=" * 80)
        self.stdout.write("")

        total_deleted = 0

        # Perform requested cleanups
        if "statuses" in cleanups:
            total_deleted += self._cleanup_statuses(dry_run, batch_size)

        if "reviews" in cleanups:
            total_deleted += self._cleanup_reviews(dry_run, batch_size)

        if "shelf-books" in cleanups:
            total_deleted += self._cleanup_shelf_books(dry_run, batch_size)

        if "list-items" in cleanups:
            total_deleted += self._cleanup_list_items(dry_run, batch_size)

        if "notifications" in cleanups:
            total_deleted += self._cleanup_notifications(dry_run, batch_size)

        if "relationships" in cleanups:
            total_deleted += self._cleanup_relationships(dry_run, batch_size)

        # Summary
        self.stdout.write("")
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.MIGRATE_HEADING("Summary"))
        self.stdout.write("-" * 80)
        
        if dry_run:
            self.stdout.write(
                f"Would delete {self.style.WARNING(str(total_deleted))} record(s)"
            )
            self.stdout.write(
                "\nRun without --dry-run to perform actual cleanup."
            )
        else:
            self.stdout.write(
                f"Deleted {self.style.SUCCESS(str(total_deleted))} record(s)"
            )
        
        self.stdout.write("=" * 80)

    def _cleanup_statuses(self, dry_run: bool, batch_size: int) -> int:
        """Clean up orphaned statuses.

        Args:
            dry_run: If True, don't actually delete
            batch_size: Number of records to delete at once

        Returns:
            Number of records deleted
        """
        self.stdout.write(self.style.MIGRATE_LABEL("Cleaning up statuses..."))

        # Find orphaned statuses (from deleted users, excluding direct messages)
        orphaned = models.Status.objects.filter(
            user__is_deleted=True
        ).exclude(privacy="direct")

        count = orphaned.count()

        if count == 0:
            self.stdout.write("  No orphaned statuses found")
            return 0

        self.stdout.write(f"  Found {count} orphaned status(es)")

        if not dry_run:
            deleted = 0
            with transaction.atomic():
                # Delete in batches
                while orphaned.exists():
                    batch = list(orphaned[:batch_size].values_list("id", flat=True))
                    models.Status.objects.filter(id__in=batch).delete()
                    deleted += len(batch)
                    self.stdout.write(f"    Deleted {deleted}/{count}...", ending="\r")
                
                self.stdout.write(f"    Deleted {deleted} status(es)    ")

        return count

    def _cleanup_reviews(self, dry_run: bool, batch_size: int) -> int:
        """Clean up orphaned reviews.

        Args:
            dry_run: If True, don't actually delete
            batch_size: Number of records to delete at once

        Returns:
            Number of records deleted
        """
        self.stdout.write(self.style.MIGRATE_LABEL("Cleaning up reviews..."))

        # Find orphaned reviews
        orphaned = models.Review.objects.filter(
            Q(book__isnull=True) | Q(user__is_deleted=True)
        )

        count = orphaned.count()

        if count == 0:
            self.stdout.write("  No orphaned reviews found")
            return 0

        self.stdout.write(f"  Found {count} orphaned review(s)")

        if not dry_run:
            deleted = 0
            with transaction.atomic():
                while orphaned.exists():
                    batch = list(orphaned[:batch_size].values_list("id", flat=True))
                    models.Review.objects.filter(id__in=batch).delete()
                    deleted += len(batch)
                    self.stdout.write(f"    Deleted {deleted}/{count}...", ending="\r")
                
                self.stdout.write(f"    Deleted {deleted} review(s)    ")

        return count

    def _cleanup_shelf_books(self, dry_run: bool, batch_size: int) -> int:
        """Clean up orphaned shelf books.

        Args:
            dry_run: If True, don't actually delete
            batch_size: Number of records to delete at once

        Returns:
            Number of records deleted
        """
        self.stdout.write(
            self.style.MIGRATE_LABEL("Cleaning up shelf books...")
        )

        # Find orphaned shelf books
        orphaned = models.ShelfBook.objects.filter(
            Q(book__isnull=True) | Q(shelf__user__is_deleted=True)
        )

        count = orphaned.count()

        if count == 0:
            self.stdout.write("  No orphaned shelf books found")
            return 0

        self.stdout.write(f"  Found {count} orphaned shelf book(s)")

        if not dry_run:
            deleted = 0
            with transaction.atomic():
                while orphaned.exists():
                    batch = list(orphaned[:batch_size].values_list("id", flat=True))
                    models.ShelfBook.objects.filter(id__in=batch).delete()
                    deleted += len(batch)
                    self.stdout.write(f"    Deleted {deleted}/{count}...", ending="\r")
                
                self.stdout.write(f"    Deleted {deleted} shelf book(s)    ")

        return count

    def _cleanup_list_items(self, dry_run: bool, batch_size: int) -> int:
        """Clean up orphaned list items.

        Args:
            dry_run: If True, don't actually delete
            batch_size: Number of records to delete at once

        Returns:
            Number of records deleted
        """
        self.stdout.write(
            self.style.MIGRATE_LABEL("Cleaning up list items...")
        )

        # Find orphaned list items
        orphaned = models.ListItem.objects.filter(
            Q(book__isnull=True) | Q(book_list__isnull=True)
        )

        count = orphaned.count()

        if count == 0:
            self.stdout.write("  No orphaned list items found")
            return 0

        self.stdout.write(f"  Found {count} orphaned list item(s)")

        if not dry_run:
            deleted = 0
            with transaction.atomic():
                while orphaned.exists():
                    batch = list(orphaned[:batch_size].values_list("id", flat=True))
                    models.ListItem.objects.filter(id__in=batch).delete()
                    deleted += len(batch)
                    self.stdout.write(f"    Deleted {deleted}/{count}...", ending="\r")
                
                self.stdout.write(f"    Deleted {deleted} list item(s)    ")

        return count

    def _cleanup_notifications(self, dry_run: bool, batch_size: int) -> int:
        """Clean up orphaned notifications.

        Args:
            dry_run: If True, don't actually delete
            batch_size: Number of records to delete at once

        Returns:
            Number of records deleted
        """
        self.stdout.write(
            self.style.MIGRATE_LABEL("Cleaning up notifications...")
        )

        # Find orphaned notifications
        orphaned = models.Notification.objects.filter(
            Q(user__is_deleted=True) | Q(related_user__is_deleted=True)
        )

        count = orphaned.count()

        if count == 0:
            self.stdout.write("  No orphaned notifications found")
            return 0

        self.stdout.write(f"  Found {count} orphaned notification(s)")

        if not dry_run:
            deleted = 0
            with transaction.atomic():
                while orphaned.exists():
                    batch = list(orphaned[:batch_size].values_list("id", flat=True))
                    models.Notification.objects.filter(id__in=batch).delete()
                    deleted += len(batch)
                    self.stdout.write(f"    Deleted {deleted}/{count}...", ending="\r")
                
                self.stdout.write(f"    Deleted {deleted} notification(s)    ")

        return count

    def _cleanup_relationships(self, dry_run: bool, batch_size: int) -> int:
        """Clean up invalid relationships.

        Args:
            dry_run: If True, don't actually delete
            batch_size: Number of records to delete at once

        Returns:
            Number of records deleted
        """
        self.stdout.write(
            self.style.MIGRATE_LABEL("Cleaning up relationships...")
        )

        total_deleted = 0

        # Clean up self-follows
        self_follows = models.UserFollows.objects.filter(
            user_subject=F("user_object")
        )

        count = self_follows.count()
        if count > 0:
            self.stdout.write(f"  Found {count} self-follow(s)")
            if not dry_run:
                self_follows.delete()
            total_deleted += count

        # Clean up orphaned relationships
        orphaned_follows = models.UserFollows.objects.filter(
            Q(user_subject__is_deleted=True) | Q(user_object__is_deleted=True)
        )

        count = orphaned_follows.count()
        if count > 0:
            self.stdout.write(f"  Found {count} orphaned follow(s)")
            if not dry_run:
                orphaned_follows.delete()
            total_deleted += count

        # Clean up orphaned blocks
        orphaned_blocks = models.UserBlocks.objects.filter(
            Q(user_subject__is_deleted=True) | Q(user_object__is_deleted=True)
        )

        count = orphaned_blocks.count()
        if count > 0:
            self.stdout.write(f"  Found {count} orphaned block(s)")
            if not dry_run:
                orphaned_blocks.delete()
            total_deleted += count

        if total_deleted == 0:
            self.stdout.write("  No invalid relationships found")

        return total_deleted
