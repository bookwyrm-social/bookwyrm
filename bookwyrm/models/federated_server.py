""" connections to external ActivityPub servers """
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
    application_type = models.CharField(max_length=255, null=True)
    application_version = models.CharField(max_length=255, null=True)

    def block(self):
        """ block a server """
        self.status = "blocked"
        self.save()
