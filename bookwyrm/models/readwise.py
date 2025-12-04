"""Models for Readwise integration - sync tracking and duplicate prevention"""

from django.db import models
from django.utils import timezone


class ReadwiseSync(models.Model):
    """Tracks sync state for a user's Readwise integration"""

    user = models.OneToOneField(
        "User",
        on_delete=models.CASCADE,
        related_name="readwise_sync",
    )
    last_export_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time quotes were exported to Readwise",
    )
    last_import_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time highlights were imported from Readwise",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Readwise Sync"
        verbose_name_plural = "Readwise Syncs"

    def __str__(self):
        return f"ReadwiseSync for {self.user.username}"

    def mark_export(self):
        """Update last export timestamp"""
        self.last_export_at = timezone.now()
        self.save(update_fields=["last_export_at", "updated_at"])

    def mark_import(self):
        """Update last import timestamp"""
        self.last_import_at = timezone.now()
        self.save(update_fields=["last_import_at", "updated_at"])


class ReadwiseSyncedHighlight(models.Model):
    """Tracks which Readwise highlights have been imported to prevent duplicates"""

    user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="readwise_highlights",
    )
    readwise_id = models.BigIntegerField(
        help_text="Highlight ID from Readwise API",
    )
    readwise_book_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Book ID from Readwise API (user_book_id)",
    )
    quotation = models.ForeignKey(
        "Quotation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="readwise_source",
        help_text="The BookWyrm quotation created from this highlight",
    )
    book_title = models.CharField(
        max_length=500,
        blank=True,
        help_text="Book title from Readwise (for reference if no match)",
    )
    book_author = models.CharField(
        max_length=500,
        blank=True,
        help_text="Book author from Readwise (for reference if no match)",
    )
    highlight_text = models.TextField(
        blank=True,
        help_text="The highlight text (stored for debugging/reference)",
    )
    imported_at = models.DateTimeField(auto_now_add=True)
    matched_book = models.ForeignKey(
        "Edition",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="readwise_highlights",
        help_text="The BookWyrm edition this was matched to",
    )

    class Meta:
        verbose_name = "Readwise Synced Highlight"
        verbose_name_plural = "Readwise Synced Highlights"
        unique_together = ["user", "readwise_id"]
        indexes = [
            models.Index(fields=["user", "readwise_book_id"]),
        ]

    def __str__(self):
        return f"Highlight {self.readwise_id} for {self.user.username}"
