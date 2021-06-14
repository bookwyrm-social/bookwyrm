""" manages interfaces with external sources of book data """
from django.db import models
from bookwyrm.connectors.settings import CONNECTORS

from .base_model import BookWyrmModel, DeactivationReason


ConnectorFiles = models.TextChoices("ConnectorFiles", CONNECTORS)


class Connector(BookWyrmModel):
    """book data source connectors"""

    identifier = models.CharField(max_length=255, unique=True)
    priority = models.IntegerField(default=2)
    name = models.CharField(max_length=255, null=True, blank=True)
    local = models.BooleanField(default=False)
    connector_file = models.CharField(max_length=255, choices=ConnectorFiles.choices)
    api_key = models.CharField(max_length=255, null=True, blank=True)
    active = models.BooleanField(default=True)
    deactivation_reason = models.CharField(
        max_length=255, choices=DeactivationReason.choices, null=True, blank=True
    )

    base_url = models.CharField(max_length=255)
    books_url = models.CharField(max_length=255)
    covers_url = models.CharField(max_length=255)
    search_url = models.CharField(max_length=255, null=True, blank=True)
    isbn_search_url = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return "{} ({})".format(
            self.identifier,
            self.id,
        )
