""" connections to external ActivityPub servers """
from urllib.parse import urlparse

from django.apps import apps
from django.db import models
from django.utils.translation import gettext_lazy as _

from .base_model import BookWyrmModel

FederationStatus = [
    ("federated", _("Federated")),
    ("blocked", _("Blocked")),
]


class FederatedServer(BookWyrmModel):
    """store which servers we federate with"""

    server_name = models.CharField(max_length=255, unique=True)
    status = models.CharField(
        max_length=255, default="federated", choices=FederationStatus
    )
    # is it mastodon, bookwyrm, etc
    application_type = models.CharField(max_length=255, null=True, blank=True)
    application_version = models.CharField(max_length=255, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    def block(self):
        """block a server"""
        self.status = "blocked"
        self.save(update_fields=["status"])

        # deactivate all associated users
        self.user_set.filter(is_active=True).update(
            is_active=False, deactivation_reason="domain_block"
        )

        # check for related connectors
        if self.application_type == "bookwyrm":
            connector_model = apps.get_model("bookwyrm.Connector", require_ready=True)
            connector_model.objects.filter(
                identifier=self.server_name, active=True
            ).update(active=False, deactivation_reason="domain_block")

    def unblock(self):
        """unblock a server"""
        self.status = "federated"
        self.save(update_fields=["status"])

        self.user_set.filter(deactivation_reason="domain_block").update(
            is_active=True, deactivation_reason=None
        )

        # check for related connectors
        if self.application_type == "bookwyrm":
            connector_model = apps.get_model("bookwyrm.Connector", require_ready=True)
            connector_model.objects.filter(
                identifier=self.server_name,
                active=False,
                deactivation_reason="domain_block",
            ).update(active=True, deactivation_reason=None)

    @classmethod
    def is_blocked(cls, url):
        """look up if a domain is blocked"""
        url = urlparse(url)
        domain = url.netloc
        return cls.objects.filter(server_name=domain, status="blocked").exists()
