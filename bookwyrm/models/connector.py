""" manages interfaces with external sources of book data """
from typing import Optional

from django.db import models
from django.utils import timezone
from bookwyrm.connectors.settings import CONNECTORS

from .base_model import BookWyrmModel, DeactivationReason


ConnectorFiles = models.TextChoices("ConnectorFiles", CONNECTORS)


class HealthStatus(models.TextChoices):
    """Connector health status choices"""

    HEALTHY = "healthy", "Healthy"
    DEGRADED = "degraded", "Degraded"
    UNAVAILABLE = "unavailable", "Unavailable"


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

    # Health tracking fields
    health_status = models.CharField(
        max_length=20,
        choices=HealthStatus.choices,
        default=HealthStatus.HEALTHY,
    )
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_failure_at = models.DateTimeField(null=True, blank=True)
    failure_count = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    avg_response_ms = models.IntegerField(null=True, blank=True)

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

    def record_success(self, latency_ms: Optional[int] = None) -> None:
        """Record a successful request"""
        self.success_count += 1
        self.last_success_at = timezone.now()

        if latency_ms is not None and latency_ms > 0:
            if self.avg_response_ms:
                # Rolling average
                total = self.success_count + self.failure_count
                self.avg_response_ms = int(
                    (self.avg_response_ms * (total - 1) + latency_ms) / total
                )
            else:
                self.avg_response_ms = latency_ms

        self._update_health_status()
        self.save(
            update_fields=[
                "success_count",
                "last_success_at",
                "avg_response_ms",
                "health_status",
            ]
        )

    def record_failure(self, latency_ms: Optional[int] = None) -> None:
        """Record a failed request"""
        self.failure_count += 1
        self.last_failure_at = timezone.now()

        self._update_health_status()
        self.save(
            update_fields=["failure_count", "last_failure_at", "health_status"]
        )

    def _update_health_status(self) -> None:
        """Update health status based on success rate"""
        total = self.success_count + self.failure_count
        if total == 0:
            self.health_status = HealthStatus.HEALTHY
            return

        success_rate = self.success_count / total

        if success_rate >= 0.95:
            self.health_status = HealthStatus.HEALTHY
        elif success_rate >= 0.7:
            self.health_status = HealthStatus.DEGRADED
        else:
            self.health_status = HealthStatus.UNAVAILABLE

    def reset_health_stats(self) -> None:
        """Reset health statistics (for manual recovery)"""
        self.failure_count = 0
        self.success_count = 0
        self.health_status = HealthStatus.HEALTHY
        self.avg_response_ms = None
        self.save(
            update_fields=[
                "failure_count",
                "success_count",
                "health_status",
                "avg_response_ms",
            ]
        )

    @property
    def success_rate(self) -> float:
        """Calculate current success rate as percentage"""
        total = self.success_count + self.failure_count
        if total == 0:
            return 100.0
        return round((self.success_count / total) * 100, 1)
