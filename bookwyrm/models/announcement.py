""" admin announcements """
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .base_model import BookWyrmModel


class Announcement(BookWyrmModel):
    """The admin has something to say"""

    user = models.ForeignKey("User", on_delete=models.PROTECT)
    preview = models.CharField(max_length=255)
    content = models.TextField(null=True, blank=True)
    event_date = models.DateTimeField(blank=True, null=True)
    start_date = models.DateTimeField(blank=True, null=True)
    end_date = models.DateTimeField(blank=True, null=True)
    active = models.BooleanField(default=True)

    @classmethod
    def active_announcements(cls):
        """announcements that should be displayed"""
        now = timezone.now()
        return cls.objects.filter(
            Q(start_date__isnull=True) | Q(start_date__lte=now),
            Q(end_date__isnull=True) | Q(end_date__gte=now),
            active=True,
        )
