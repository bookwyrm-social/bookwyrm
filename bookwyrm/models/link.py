""" outlink data """
from urllib.parse import urlparse

from django.core.exceptions import PermissionDenied
from django.db import models
from django.utils.translation import gettext_lazy as _

from bookwyrm import activitypub
from .activitypub_mixin import ActivitypubMixin
from .base_model import BookWyrmModel
from . import fields


class Link(ActivitypubMixin, BookWyrmModel):
    """a link to a website"""

    url = fields.URLField(max_length=255, activitypub_field="href")
    added_by = fields.ForeignKey(
        "User", on_delete=models.SET_NULL, null=True, activitypub_field="attributedTo"
    )
    domain = models.ForeignKey(
        "LinkDomain",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="links",
    )

    activity_serializer = activitypub.Link
    reverse_unfurl = True

    @property
    def name(self):
        """link name via the assocaited domain"""
        return self.domain.name

    def save(self, *args, **kwargs):
        """create a link"""
        # get or create the associated domain
        if not self.domain:
            domain = urlparse(self.url).netloc
            self.domain, _ = LinkDomain.objects.get_or_create(domain=domain)

        # this is never broadcast, the owning model broadcasts an update
        if "broadcast" in kwargs:
            del kwargs["broadcast"]
        return super().save(*args, **kwargs)


AvailabilityChoices = [
    ("free", _("Free")),
    ("purchase", _("Purchasable")),
    ("loan", _("Available for loan")),
]


class FileLink(Link):
    """a link to a file"""

    book = models.ForeignKey(
        "Book", on_delete=models.CASCADE, related_name="file_links", null=True
    )
    filetype = fields.CharField(max_length=50, activitypub_field="mediaType")
    availability = fields.CharField(
        max_length=100, choices=AvailabilityChoices, default="free"
    )


StatusChoices = [
    ("approved", _("Approved")),
    ("blocked", _("Blocked")),
    ("pending", _("Pending")),
]


class LinkDomain(BookWyrmModel):
    """List of domains used in links"""

    domain = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=50, choices=StatusChoices, default="pending")
    name = models.CharField(max_length=100)
    reported_by = models.ForeignKey(
        "User", blank=True, null=True, on_delete=models.SET_NULL
    )

    def raise_not_editable(self, viewer):
        if viewer.has_perm("moderate_post"):
            return
        raise PermissionDenied()

    def save(self, *args, **kwargs):
        """set a default name"""
        if not self.name:
            self.name = self.domain
        super().save(*args, **kwargs)
