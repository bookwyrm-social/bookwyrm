""" connections to external ActivityPub servers """
from urllib.parse import urlparse
from django.db import models
from .base_model import BookWyrmModel

FederationStatus = models.TextChoices(
    "Status",
    [
        "federated",
        "blocked",
    ],
)


class FederatedServer(BookWyrmModel):
    """ store which servers we federate with """

    server_name = models.CharField(max_length=255, unique=True)
    status = models.CharField(
        max_length=255, default="federated", choices=FederationStatus.choices
    )
    # is it mastodon, bookwyrm, etc
    application_type = models.CharField(max_length=255, null=True, blank=True)
    application_version = models.CharField(max_length=255, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    def block(self):
        """ block a server """
        self.status = "blocked"
        self.save()

        # deactivate all associated users
        self.user_set.filter(is_active=True).update(
            is_active=False, deactivation_reason="domain_block"
        )

    def unblock(self):
        """ unblock a server """
        self.status = "federated"
        self.save()

        self.user_set.filter(deactivation_reason="domain_block").update(
            is_active=True, deactivation_reason=None
        )

    @classmethod
    def is_blocked(cls, url):
        """ look up if a domain is blocked """
        url = urlparse(url)
        domain = url.netloc
        return cls.objects.filter(server_name=domain, status="blocked").exists()
