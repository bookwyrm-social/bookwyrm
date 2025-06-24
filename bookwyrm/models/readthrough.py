""" progress in a book """
from typing import Optional, Iterable

from django.core import validators
from django.core.cache import cache
from django.db import models
from django.db.models import F, Q

from bookwyrm.utils.db import add_update_fields

from .base_model import BookWyrmModel


class ProgressMode(models.TextChoices):
    """types of progress available"""

    PAGE = "PG", "page"
    PERCENT = "PCT", "percent"


class ReadThrough(BookWyrmModel):
    """Store a read through a book in the database."""

    user = models.ForeignKey("User", on_delete=models.PROTECT)
    book = models.ForeignKey("Edition", on_delete=models.PROTECT)
    progress = models.IntegerField(
        validators=[validators.MinValueValidator(0)], null=True, blank=True
    )
    progress_mode = models.CharField(
        max_length=3, choices=ProgressMode.choices, default=ProgressMode.PAGE
    )
    start_date = models.DateTimeField(blank=True, null=True)
    finish_date = models.DateTimeField(blank=True, null=True)
    stopped_date = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def save(self, *args, update_fields: Optional[Iterable[str]] = None, **kwargs):
        """update user active time"""
        # an active readthrough must have an unset finish date
        if self.finish_date or self.stopped_date:
            self.is_active = False
            update_fields = add_update_fields(update_fields, "is_active")

        super().save(*args, update_fields=update_fields, **kwargs)

        cache.delete(f"latest_read_through-{self.user_id}-{self.book_id}")
        self.user.update_active_date()

    def create_update(self):
        """add update to the readthrough"""
        if self.progress:
            return self.progressupdate_set.create(
                user=self.user, progress=self.progress, mode=self.progress_mode
            )
        return None

    class Meta:
        """Don't let readthroughs end before they start"""

        constraints = [
            models.CheckConstraint(
                condition=Q(finish_date__gte=F("start_date")), name="chronology"
            )
        ]
        ordering = ("-start_date",)


class ProgressUpdate(BookWyrmModel):
    """Store progress through a book in the database."""

    user = models.ForeignKey("User", on_delete=models.PROTECT)
    readthrough = models.ForeignKey("ReadThrough", on_delete=models.CASCADE)
    progress = models.IntegerField(validators=[validators.MinValueValidator(0)])
    mode = models.CharField(
        max_length=3, choices=ProgressMode.choices, default=ProgressMode.PAGE
    )

    def save(self, *args, **kwargs):
        """update user active time"""
        self.user.update_active_date()
        super().save(*args, **kwargs)
