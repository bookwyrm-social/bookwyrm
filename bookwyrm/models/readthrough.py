""" progress in a book """
from django.core import validators
from django.db import models
from django.db.models import F, Q

from .base_model import BookWyrmModel


class ProgressMode(models.TextChoices):
    """types of prgress available"""

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
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        """update user active time"""
        self.user.update_active_date()
        # an active readthrough must have an unset finish date
        if self.finish_date:
            self.is_active = False
        super().save(*args, **kwargs)

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
                check=Q(finish_date__gte=F("start_date")), name="chronology"
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
