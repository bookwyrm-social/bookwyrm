''' connections to external ActivityPub servers '''
from django.db import models
from .base_model import BookWyrmModel


class FederatedServer(BookWyrmModel):
    ''' store which server's we federate with '''
    server_name = models.CharField(max_length=255, unique=True)
    # federated, blocked, whatever else
    status = models.CharField(max_length=255, default='federated')
    # is it mastodon, bookwyrm, etc
    application_type = models.CharField(max_length=255, null=True)
    application_version = models.CharField(max_length=255, null=True)

# TODO: blocked servers
