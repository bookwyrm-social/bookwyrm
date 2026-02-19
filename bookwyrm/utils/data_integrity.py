"""Data integrity checking utilities for BookWyrm.

Provides tools for validating data consistency, detecting orphaned records,
checking foreign key integrity, and validating ActivityPub data.
"""

import logging
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from django.db import connection, models as django_models
from django.db.models import Count, F, Q, Exists, OuterRef
from django.apps import apps

from bookwyrm import models

logger = logging.getLogger(__name__)


class DataIntegrityChecker:
    """Checks data integrity across the database."""

    def __init__(self):
        """Initialize the data integrity checker."""
        self.issues: List[Dict] = []
        self.warnings: List[Dict] = []

    def check_all(self) -> Dict:
        """Run all data integrity checks.

        Returns:
            Dictionary with check results
        """
        self.issues = []
        self.warnings = []

        self.check_orphaned_statuses()
        self.check_orphaned_reviews()
        self.check_orphaned_shelf_books()
        self.check_orphaned_list_items()
        self.check_orphaned_notifications()
        self.check_user_relationships()
        self.check_book_relationships()
        self.check_federation_data()
        self.check_missing_remote_ids()

        return {
            "issues": self.issues,
            "warnings": self.warnings,
            "issue_count": len(self.issues),
            "warning_count": len(self.warnings),
        }

    def check_orphaned_statuses(self):
        """Check for orphaned status objects."""
        try:
            # Find statuses with deleted users
            orphaned = models.Status.objects.filter(
                user__is_deleted=True
            ).exclude(
                privacy="direct"  # Keep direct messages for data retention
            ).count()

            if orphaned > 0:
                self.issues.append({
                    "type": "orphaned_data",
                    "model": "Status",
                    "count": orphaned,
                    "description": f"Found {orphaned} status(es) from deleted users",
                    "action": "Run cleanup command or manually delete",
                })

            # Find statuses referencing non-existent books
            orphaned_books = models.Status.objects.filter(
                Q(mention_books__isnull=False, mention_books__deleted=True)
            ).distinct().count()

            if orphaned_books > 0:
                self.warnings.append({
                    "type": "orphaned_reference",
                    "model": "Status",
                    "count": orphaned_books,
                    "description": f"Found {orphaned_books} status(es) referencing deleted books",
                })

        except Exception as e:
            logger.error(f"Error checking orphaned statuses: {e}")

    def check_orphaned_reviews(self):
        """Check for orphaned review objects."""
        try:
            # Find reviews with deleted books
            orphaned = models.Review.objects.filter(
                book__isnull=True
            ).count()

            if orphaned > 0:
                self.issues.append({
                    "type": "orphaned_data",
                    "model": "Review",
                    "count": orphaned,
                    "description": f"Found {orphaned} review(s) with missing books",
                    "action": "Delete orphaned reviews",
                })

            # Find reviews with deleted users
            orphaned_users = models.Review.objects.filter(
                user__is_deleted=True
            ).count()

            if orphaned_users > 0:
                self.issues.append({
                    "type": "orphaned_data",
                    "model": "Review",
                    "count": orphaned_users,
                    "description": f"Found {orphaned_users} review(s) from deleted users",
                    "action": "Run cleanup command",
                })

        except Exception as e:
            logger.error(f"Error checking orphaned reviews: {e}")

    def check_orphaned_shelf_books(self):
        """Check for orphaned shelf book entries."""
        try:
            # Find shelf books with deleted books
            orphaned_books = models.ShelfBook.objects.filter(
                book__isnull=True
            ).count()

            if orphaned_books > 0:
                self.issues.append({
                    "type": "orphaned_data",
                    "model": "ShelfBook",
                    "count": orphaned_books,
                    "description": f"Found {orphaned_books} shelf entries with missing books",
                    "action": "Delete orphaned shelf entries",
                })

            # Find shelf books with deleted users
            orphaned_users = models.ShelfBook.objects.filter(
                shelf__user__is_deleted=True
            ).count()

            if orphaned_users > 0:
                self.issues.append({
                    "type": "orphaned_data",
                    "model": "ShelfBook",
                    "count": orphaned_users,
                    "description": f"Found {orphaned_users} shelf entries from deleted users",
                    "action": "Run cleanup command",
                })

        except Exception as e:
            logger.error(f"Error checking orphaned shelf books: {e}")

    def check_orphaned_list_items(self):
        """Check for orphaned list items."""
        try:
            # Find list items with deleted books
            orphaned = models.ListItem.objects.filter(
                book__isnull=True
            ).count()

            if orphaned > 0:
                self.issues.append({
                    "type": "orphaned_data",
                    "model": "ListItem",
                    "count": orphaned,
                    "description": f"Found {orphaned} list item(s) with missing books",
                    "action": "Delete orphaned list items",
                })

            # Find list items in deleted lists
            orphaned_lists = models.ListItem.objects.filter(
                book_list__isnull=True
            ).count()

            if orphaned_lists > 0:
                self.issues.append({
                    "type": "orphaned_data",
                    "model": "ListItem",
                    "count": orphaned_lists,
                    "description": f"Found {orphaned_lists} list item(s) with missing lists",
                    "action": "Delete orphaned list items",
                })

        except Exception as e:
            logger.error(f"Error checking orphaned list items: {e}")

    def check_orphaned_notifications(self):
        """Check for orphaned notifications."""
        try:
            # Find notifications for deleted users
            orphaned = models.Notification.objects.filter(
                Q(user__is_deleted=True) | Q(related_user__is_deleted=True)
            ).count()

            if orphaned > 0:
                self.warnings.append({
                    "type": "orphaned_data",
                    "model": "Notification",
                    "count": orphaned,
                    "description": f"Found {orphaned} notification(s) for deleted users",
                    "action": "Clean up old notifications",
                })

        except Exception as e:
            logger.error(f"Error checking orphaned notifications: {e}")

    def check_user_relationships(self):
        """Check user relationship integrity."""
        try:
            # Find self-follows
            self_follows = models.UserFollows.objects.filter(
                user_subject=F("user_object")
            ).count()

            if self_follows > 0:
                self.issues.append({
                    "type": "invalid_relationship",
                    "model": "UserFollows",
                    "count": self_follows,
                    "description": f"Found {self_follows} user(s) following themselves",
                    "action": "Delete self-follow relationships",
                })

            # Find duplicate follows
            duplicate_follows = (
                models.UserFollows.objects.values("user_subject", "user_object")
                .annotate(count=Count("id"))
                .filter(count__gt=1)
                .count()
            )

            if duplicate_follows > 0:
                self.issues.append({
                    "type": "duplicate_data",
                    "model": "UserFollows",
                    "count": duplicate_follows,
                    "description": f"Found {duplicate_follows} duplicate follow relationship(s)",
                    "action": "Remove duplicate relationships",
                })

            # Find blocks with deleted users
            orphaned_blocks = models.UserBlocks.objects.filter(
                Q(user_subject__is_deleted=True) | Q(user_object__is_deleted=True)
            ).count()

            if orphaned_blocks > 0:
                self.warnings.append({
                    "type": "orphaned_data",
                    "model": "UserBlocks",
                    "count": orphaned_blocks,
                    "description": f"Found {orphaned_blocks} block(s) involving deleted users",
                })

        except Exception as e:
            logger.error(f"Error checking user relationships: {e}")

    def check_book_relationships(self):
        """Check book relationship integrity."""
        try:
            # Find editions without parent works
            orphaned_editions = models.Edition.objects.filter(
                parent_work__isnull=True
            ).count()

            if orphaned_editions > 0:
                self.warnings.append({
                    "type": "missing_relationship",
                    "model": "Edition",
                    "count": orphaned_editions,
                    "description": f"Found {orphaned_editions} edition(s) without parent works",
                    "action": "Consider linking editions to works",
                })

            # Find works without any editions
            works_without_editions = models.Work.objects.annotate(
                has_editions=Exists(
                    models.Edition.objects.filter(parent_work=OuterRef("pk"))
                )
            ).filter(has_editions=False).count()

            if works_without_editions > 0:
                self.warnings.append({
                    "type": "missing_relationship",
                    "model": "Work",
                    "count": works_without_editions,
                    "description": f"Found {works_without_editions} work(s) without editions",
                })

            # Find books without authors
            books_without_authors = models.Edition.objects.annotate(
                author_count=Count("authors")
            ).filter(author_count=0).count()

            if books_without_authors > 0:
                self.warnings.append({
                    "type": "missing_relationship",
                    "model": "Edition",
                    "count": books_without_authors,
                    "description": f"Found {books_without_authors} book(s) without authors",
                })

        except Exception as e:
            logger.error(f"Error checking book relationships: {e}")

    def check_federation_data(self):
        """Check ActivityPub federation data integrity."""
        try:
            # Find remote users without federation servers
            remote_users_no_server = models.User.objects.filter(
                local=False, federated_server__isnull=True
            ).count()

            if remote_users_no_server > 0:
                self.issues.append({
                    "type": "missing_relationship",
                    "model": "User (remote)",
                    "count": remote_users_no_server,
                    "description": f"Found {remote_users_no_server} remote user(s) without federated server",
                    "action": "Link users to federated servers",
                })

            # Find statuses from local users marked as remote
            invalid_status_ownership = models.Status.objects.filter(
                user__local=True, remote_id__isnull=False
            ).exclude(remote_id="").count()

            if invalid_status_ownership > 0:
                self.warnings.append({
                    "type": "inconsistent_data",
                    "model": "Status",
                    "count": invalid_status_ownership,
                    "description": f"Found {invalid_status_ownership} status(es) from local users with remote IDs",
                })

        except Exception as e:
            logger.error(f"Error checking federation data: {e}")

    def check_missing_remote_ids(self):
        """Check for federated objects missing remote IDs."""
        try:
            # Remote users should have remote_id
            remote_users_no_id = models.User.objects.filter(
                local=False
            ).filter(
                Q(remote_id__isnull=True) | Q(remote_id="")
            ).count()

            if remote_users_no_id > 0:
                self.issues.append({
                    "type": "missing_data",
                    "model": "User (remote)",
                    "count": remote_users_no_id,
                    "description": f"Found {remote_users_no_id} remote user(s) without remote_id",
                    "action": "Fix remote user data",
                })

            # Remote statuses should have remote_id
            remote_statuses_no_id = models.Status.objects.filter(
                user__local=False
            ).filter(
                Q(remote_id__isnull=True) | Q(remote_id="")
            ).count()

            if remote_statuses_no_id > 0:
                self.issues.append({
                    "type": "missing_data",
                    "model": "Status (remote)",
                    "count": remote_statuses_no_id,
                    "description": f"Found {remote_statuses_no_id} remote status(es) without remote_id",
                })

        except Exception as e:
            logger.error(f"Error checking remote IDs: {e}")

    def get_summary(self) -> Dict:
        """Get summary of all integrity checks.

        Returns:
            Dictionary with summary information
        """
        critical_count = sum(
            1 for issue in self.issues if issue["type"] == "orphaned_data"
        )
        
        return {
            "total_issues": len(self.issues),
            "total_warnings": len(self.warnings),
            "critical_issues": critical_count,
            "issues": self.issues,
            "warnings": self.warnings,
        }


def find_duplicate_records(model_class, fields: List[str]) -> List[Dict]:
    """Find duplicate records in a model based on specified fields.

    Args:
        model_class: Django model class
        fields: List of field names to check for duplicates

    Returns:
        List of duplicate record information
    """
    try:
        duplicates = (
            model_class.objects.values(*fields)
            .annotate(count=Count("id"))
            .filter(count__gt=1)
            .order_by("-count")
        )

        result = []
        for dup in duplicates:
            result.append({
                "fields": {field: dup[field] for field in fields},
                "count": dup["count"],
                "model": model_class.__name__,
            })

        return result

    except Exception as e:
        logger.error(f"Error finding duplicates in {model_class.__name__}: {e}")
        return []


def validate_foreign_keys() -> List[Dict]:
    """Validate foreign key constraints across all models.

    Returns:
        List of foreign key validation issues
    """
    issues = []

    try:
        # Get all models
        all_models = apps.get_models()

        for model in all_models:
            # Skip models without foreign keys
            foreign_keys = [
                field for field in model._meta.get_fields()
                if isinstance(field, django_models.ForeignKey)
            ]

            if not foreign_keys:
                continue

            for fk in foreign_keys:
                # Check for null foreign keys (if not allowed)
                if not fk.null:
                    null_count = model.objects.filter(
                        **{f"{fk.name}__isnull": True}
                    ).count()

                    if null_count > 0:
                        issues.append({
                            "type": "null_foreign_key",
                            "model": model.__name__,
                            "field": fk.name,
                            "count": null_count,
                            "description": f"Found {null_count} record(s) with null {fk.name}",
                        })

    except Exception as e:
        logger.error(f"Error validating foreign keys: {e}")

    return issues
