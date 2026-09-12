"""progress in a book"""

from typing import Optional, Iterable

from django.core import validators
from django.core.cache import cache
from django.db import models
from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _

from bookwyrm.utils.db import add_update_fields

from .base_model import BookWyrmModel


class ProgressMode(models.TextChoices):
    """types of progress available"""

    PAGE = "PG", "page"
    PERCENT = "PCT", "percent"


# TODO: this should use the constants in models.Shelf, but they won't stay there so
# I'm not doing it yet.
ReadingStatuses = [
    ("to-read", _("To Read")),
    ("reading", _("Currently Reading")),
    ("read", _("Read")),
    ("stopped-reading", _("Stopped Reading")),
]


class ReadThrough(BookWyrmModel):
    """Stores a user's reading history"""

    read_status = models.CharField(
        # TODO: "read" seems like the safest default value for the initial migration,
        # but its probably not the one we want long term.
        max_length=20,
        choices=ReadingStatuses,
        default="read",
    )
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

    def save(self, *args, **kwargs):
        """update user active time and tend to caches"""
        cache.delete(f"latest_read_through-{self.user.id}-{self.book.id}")
        self.user.update_active_date()
        super().save(*args, **kwargs)

    def create_update(self):
        """add update to the readthrough"""
        if self.progress:
            return self.progressupdate_set.create(
                user=self.user, progress=self.progress, mode=self.progress_mode
            )
        return None

    class Meta:
        """This is an involved one! There are logical limits on this"""

        constraints = [
            # Don't let readthroughs end before they start
            models.CheckConstraint(
                condition=check=Q(finish_date__gte=F("start_date")), name="chronology"
            ),
            # Can't be actively reading the same book twice
            # Currently reading status can't have stopped date
            # models.CheckConstraint(
            #    check=~Q(read_status="to-read", finish_date__isnull=False),
            #    name="currently-reading"
            # ),
            # Can't want to read and have started or finished dates
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
