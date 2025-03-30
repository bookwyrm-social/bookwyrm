""" manages interfaces with external sources of book data """
from typing import Optional

from django.db import models
from bookwyrm.connectors.settings import CONNECTORS

from .base_model import BookWyrmModel, DeactivationReason


ConnectorFiles = models.TextChoices("ConnectorFiles", CONNECTORS)


class Connector(BookWyrmModel):
    """book data source connectors"""

    identifier = models.CharField(max_length=255, unique=True)  # domain
    priority = models.IntegerField(default=2)
    name = models.CharField(max_length=255, null=True, blank=True)
    connector_file = models.CharField(max_length=255, choices=ConnectorFiles.choices)
    api_key = models.CharField(max_length=255, null=True, blank=True)
    active = models.BooleanField(default=True)
    deactivation_reason = models.CharField(
        max_length=255, choices=DeactivationReason, null=True, blank=True
    )

    base_url = models.CharField(max_length=255)
    books_url = models.CharField(max_length=255)
    covers_url = models.CharField(max_length=255)
    search_url = models.CharField(max_length=255, null=True, blank=True)
    isbn_search_url = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.identifier} ({self.id})"

    def deactivate(self, reason: Optional[str] = None) -> None:
        """Make an active connector inactive. We do not delete connectors
        because they have books and authors associated with them."""

        self.active = False
        self.deactivation_reason = reason
        self.save(update_fields=["active", "deactivation_reason"])

    def activate(self) -> None:
        """Make an inactive connector active again"""

        self.active = True
        self.deactivation_reason = None
        self.save(update_fields=["active", "deactivation_reason"])

    def change_priority(self, priority: int) -> None:
        """Change the priority value for a connector
        This determines the order they appear in book search"""

        self.priority = priority
        self.save(update_fields=["priority"])

    def update(self) -> None:
        """Update the settings for this connector. e.g. if the
        API endpoints change."""

        # example
        # if self.identifier == "openlibrary.org":
        #     self.isbn_search_url = "https://openlibrary.org/search.json?isbn="
        #     self.save(update_fields=["isbn_search_url"])
