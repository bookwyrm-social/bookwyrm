"""
Connector health tracking and exponential backoff for failing connectors.

Implements progressive retry delays with automatic recovery:
- Attempt 1: Immediate
- Attempt 2: 2s delay
- Attempt 3: 4s delay
- ...
- Maximum: 300s (5 minutes)
- Recovery: After 1 hour of no failures
"""
import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from django.core.cache import cache
from django.utils import timezone

from bookwyrm import models
from bookwyrm.tasks import app, CONNECTORS

logger = logging.getLogger(__name__)


class ConnectorBackoff:
    """Track and manage exponential backoff for failing connectors"""

    BACKOFF_BASE = 2  # Base multiplier for exponential backoff (seconds)
    MAX_BACKOFF = 300  # Maximum backoff delay (5 minutes)
    RESET_AFTER = 3600  # Reset after 1 hour of success (seconds)
    DEGRADED_THRESHOLD = 0.7  # 70% success rate = degraded
    UNAVAILABLE_THRESHOLD = 0.3  # 30% success rate = unavailable
    CACHE_PREFIX = "connector_backoff"
    STATS_CACHE_PREFIX = "connector_stats"
    STATS_WINDOW = 3600  # Track stats over 1 hour window

    @classmethod
    def _get_cache_key(cls, connector_id: str) -> str:
        """Generate cache key for connector"""
        return f"{cls.CACHE_PREFIX}:{connector_id}"

    @classmethod
    def _get_stats_key(cls, connector_id: str) -> str:
        """Generate cache key for connector stats"""
        return f"{cls.STATS_CACHE_PREFIX}:{connector_id}"

    @classmethod
    def should_skip(cls, connector_id: str) -> bool:
        """
        Check if we should skip this connector due to backoff.

        Returns True if currently in backoff period, False otherwise.
        """
        cache_key = cls._get_cache_key(connector_id)
        data = cache.get(cache_key)

        if not data:
            return False

        try:
            backoff_data = json.loads(data)
            next_retry_str = backoff_data.get("next_retry")

            if not next_retry_str:
                return False

            next_retry = datetime.fromisoformat(next_retry_str)
            now = datetime.utcnow()

            # Check if we should reset (1 hour elapsed since first failure)
            first_failure_str = backoff_data.get("first_failure")
            if first_failure_str:
                first_failure = datetime.fromisoformat(first_failure_str)
                if (now - first_failure).total_seconds() >= cls.RESET_AFTER:
                    cache.delete(cache_key)
                    logger.info(f"Auto-reset backoff for connector {connector_id}")
                    return False

            # Check if still in backoff period
            if now < next_retry:
                logger.debug(
                    f"Skipping connector {connector_id}, in backoff until {next_retry}"
                )
                return True

            return False

        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning(f"Error parsing backoff data for {connector_id}: {exc}")
            cache.delete(cache_key)
            return False

    @classmethod
    def record_failure(
        cls, connector_id: str, error_type: str = "unknown", latency_ms: int = 0
    ) -> None:
        """
        Record a failed request and update backoff schedule.

        Args:
            connector_id: The connector identifier
            error_type: Type of error (timeout, http_error, parse_error, etc.)
            latency_ms: Request latency in milliseconds (if available)
        """
        cache_key = cls._get_cache_key(connector_id)
        data = cache.get(cache_key)
        now = datetime.utcnow()

        if data:
            try:
                backoff_data = json.loads(data)
                failure_count = backoff_data.get("failure_count", 0) + 1
                first_failure = datetime.fromisoformat(
                    backoff_data.get("first_failure", now.isoformat())
                )
            except (json.JSONDecodeError, ValueError):
                failure_count = 1
                first_failure = now
        else:
            failure_count = 1
            first_failure = now

        # Calculate exponential backoff (capped at MAX_BACKOFF)
        backoff_seconds = min(cls.BACKOFF_BASE ** (failure_count - 1), cls.MAX_BACKOFF)
        next_retry = now + timedelta(seconds=backoff_seconds)

        backoff_data = {
            "failure_count": failure_count,
            "last_failure": now.isoformat(),
            "next_retry": next_retry.isoformat(),
            "first_failure": first_failure.isoformat(),
            "last_error_type": error_type,
        }

        # Store with TTL
        cache.set(cache_key, json.dumps(backoff_data), cls.RESET_AFTER)

        # Update rolling stats
        cls._update_stats(connector_id, success=False, latency_ms=latency_ms)

        logger.info(
            f"Recorded failure #{failure_count} for connector {connector_id} "
            f"({error_type}), next retry in {backoff_seconds}s"
        )

    @classmethod
    def record_success(cls, connector_id: str, latency_ms: int = 0) -> None:
        """
        Record a successful request and clear backoff state.

        Args:
            connector_id: The connector identifier
            latency_ms: Request latency in milliseconds
        """
        cache_key = cls._get_cache_key(connector_id)

        if cache.get(cache_key):
            cache.delete(cache_key)
            logger.info(f"Cleared backoff for connector {connector_id} after success")

        # Update rolling stats
        cls._update_stats(connector_id, success=True, latency_ms=latency_ms)

    @classmethod
    def _update_stats(
        cls, connector_id: str, success: bool, latency_ms: int = 0
    ) -> None:
        """Update rolling statistics for connector"""
        stats_key = cls._get_stats_key(connector_id)
        data = cache.get(stats_key)

        if data:
            try:
                stats = json.loads(data)
            except json.JSONDecodeError:
                stats = cls._empty_stats()
        else:
            stats = cls._empty_stats()

        # Update counters
        if success:
            stats["success_count"] += 1
        else:
            stats["failure_count"] += 1

        # Update latency (rolling average)
        if latency_ms > 0:
            total_requests = stats["success_count"] + stats["failure_count"]
            if total_requests > 1:
                stats["avg_latency_ms"] = int(
                    (stats["avg_latency_ms"] * (total_requests - 1) + latency_ms)
                    / total_requests
                )
            else:
                stats["avg_latency_ms"] = latency_ms

        stats["last_updated"] = datetime.utcnow().isoformat()

        cache.set(stats_key, json.dumps(stats), cls.STATS_WINDOW)

    @classmethod
    def _empty_stats(cls) -> dict:
        """Return empty stats structure"""
        return {
            "success_count": 0,
            "failure_count": 0,
            "avg_latency_ms": 0,
            "last_updated": None,
        }

    @classmethod
    def get_health_stats(cls, connector_id: str) -> dict:
        """
        Get current health statistics for a connector.

        Returns:
            Dict with success_rate, failure_count, avg_latency_ms, health_status
        """
        stats_key = cls._get_stats_key(connector_id)
        cache_key = cls._get_cache_key(connector_id)

        # Get rolling stats
        stats_data = cache.get(stats_key)
        if stats_data:
            try:
                stats = json.loads(stats_data)
            except json.JSONDecodeError:
                stats = cls._empty_stats()
        else:
            stats = cls._empty_stats()

        # Get backoff state
        backoff_data = cache.get(cache_key)
        in_backoff = False
        consecutive_failures = 0

        if backoff_data:
            try:
                backoff = json.loads(backoff_data)
                consecutive_failures = backoff.get("failure_count", 0)
                next_retry_str = backoff.get("next_retry")
                if next_retry_str:
                    next_retry = datetime.fromisoformat(next_retry_str)
                    in_backoff = datetime.utcnow() < next_retry
            except (json.JSONDecodeError, ValueError):
                pass

        # Calculate success rate
        total = stats["success_count"] + stats["failure_count"]
        if total > 0:
            success_rate = stats["success_count"] / total
        else:
            success_rate = 1.0  # Assume healthy if no data

        # Determine health status
        if in_backoff or success_rate < cls.UNAVAILABLE_THRESHOLD:
            health_status = "unavailable"
        elif success_rate < cls.DEGRADED_THRESHOLD:
            health_status = "degraded"
        else:
            health_status = "healthy"

        return {
            "success_count": stats["success_count"],
            "failure_count": stats["failure_count"],
            "success_rate": round(success_rate * 100, 1),
            "avg_latency_ms": stats["avg_latency_ms"],
            "health_status": health_status,
            "in_backoff": in_backoff,
            "consecutive_failures": consecutive_failures,
        }

    @classmethod
    def get_all_connector_stats(cls) -> list:
        """Get health stats for all active connectors"""
        connectors = models.Connector.objects.filter(active=True)
        return [
            {
                "identifier": c.identifier,
                "name": c.name or c.identifier,
                "priority": c.priority,
                **cls.get_health_stats(c.identifier),
            }
            for c in connectors
        ]


@app.task(queue=CONNECTORS)
def sync_connector_health() -> dict:
    """
    Periodic task to sync connector health stats to database.

    This task should be run every 5 minutes via Celery beat.
    """
    updated = 0
    connectors = models.Connector.objects.filter(active=True)

    for connector in connectors:
        stats = ConnectorBackoff.get_health_stats(connector.identifier)

        # Check if model has health fields (after migration)
        if hasattr(connector, "health_status"):
            try:
                connector.health_status = stats["health_status"]
                connector.save(update_fields=["health_status"])
                updated += 1
            except Exception as e:
                logger.error(f"Failed to update connector {connector.identifier}: {e}")

    logger.info(f"Synced health status for {updated} connectors")
    return {"updated": updated}
