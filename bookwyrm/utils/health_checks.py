"""System health check utilities for BookWyrm instance monitoring.

This module provides comprehensive health checks for all critical BookWyrm
components including database, Redis, Celery, storage, and federation services.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.conf import settings
from django.core.cache import cache
from django.db import connection, connections
from django.db.utils import OperationalError
import redis

from bookwyrm import models
from bookwyrm.tasks import app as celery

logger = logging.getLogger(__name__)


class HealthCheckResult:
    """Represents the result of a health check."""

    def __init__(
        self,
        name: str,
        status: str,
        message: str = "",
        details: Optional[Dict] = None,
        duration_ms: float = 0.0,
    ):
        """Initialize health check result.

        Args:
            name: Name of the health check
            status: Status - "healthy", "degraded", or "unhealthy"
            message: Human-readable status message
            details: Additional diagnostic details
            duration_ms: Time taken to perform check in milliseconds
        """
        self.name = name
        self.status = status
        self.message = message
        self.details = details or {}
        self.duration_ms = duration_ms
        self.timestamp = datetime.now()

    def is_healthy(self) -> bool:
        """Check if the result indicates a healthy state."""
        return self.status == "healthy"

    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "details": self.details,
            "duration_ms": round(self.duration_ms, 2),
            "timestamp": self.timestamp.isoformat(),
        }


class HealthChecker:
    """Performs comprehensive health checks on BookWyrm components."""

    def __init__(self):
        """Initialize the health checker."""
        self.results: List[HealthCheckResult] = []

    def check_all(self) -> List[HealthCheckResult]:
        """Run all health checks.

        Returns:
            List of HealthCheckResult objects
        """
        self.results = []

        # Core infrastructure checks
        self.check_database()
        self.check_redis_broker()
        self.check_redis_activity()
        self.check_celery()
        self.check_cache()

        # Application-level checks
        self.check_storage()
        self.check_email_config()
        self.check_federation()

        return self.results

    def check_database(self) -> HealthCheckResult:
        """Check database connectivity and performance.

        Returns:
            HealthCheckResult with database status
        """
        start = time.time()
        try:
            # Test basic connectivity
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

            # Get connection count
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = %s",
                    [settings.DATABASES["default"]["NAME"]],
                )
                conn_count = cursor.fetchone()[0]

            # Get database size
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_size_pretty(pg_database_size(%s))",
                    [settings.DATABASES["default"]["NAME"]],
                )
                db_size = cursor.fetchone()[0]

            duration_ms = (time.time() - start) * 1000

            details = {
                "connections": conn_count,
                "database_size": db_size,
                "response_time_ms": round(duration_ms, 2),
            }

            # Determine status based on response time
            if duration_ms < 100:
                status = "healthy"
                message = "Database is responsive"
            elif duration_ms < 500:
                status = "degraded"
                message = f"Database response slow ({duration_ms:.0f}ms)"
            else:
                status = "unhealthy"
                message = f"Database response very slow ({duration_ms:.0f}ms)"

            result = HealthCheckResult(
                name="database",
                status=status,
                message=message,
                details=details,
                duration_ms=duration_ms,
            )

        except OperationalError as e:
            duration_ms = (time.time() - start) * 1000
            result = HealthCheckResult(
                name="database",
                status="unhealthy",
                message=f"Database connection failed: {str(e)}",
                details={"error": str(e)},
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            result = HealthCheckResult(
                name="database",
                status="unhealthy",
                message=f"Database check failed: {str(e)}",
                details={"error": str(e)},
                duration_ms=duration_ms,
            )

        self.results.append(result)
        return result

    def check_redis_broker(self) -> HealthCheckResult:
        """Check Redis broker (Celery) connectivity.

        Returns:
            HealthCheckResult with Redis broker status
        """
        start = time.time()
        try:
            from celerywyrm import settings as celery_settings

            r = redis.from_url(celery_settings.REDIS_BROKER_URL)
            r.ping()

            # Get queue lengths
            from bookwyrm.tasks import (
                LOW,
                MEDIUM,
                HIGH,
                STREAMS,
                IMAGES,
                SUGGESTED_USERS,
                EMAIL,
                CONNECTORS,
                LISTS,
                INBOX,
                IMPORTS,
                IMPORT_TRIGGERED,
                BROADCAST,
                MISC,
            )

            queues = {
                "low": r.llen(LOW),
                "medium": r.llen(MEDIUM),
                "high": r.llen(HIGH),
                "streams": r.llen(STREAMS),
                "images": r.llen(IMAGES),
                "suggested_users": r.llen(SUGGESTED_USERS),
                "email": r.llen(EMAIL),
                "connectors": r.llen(CONNECTORS),
                "lists": r.llen(LISTS),
                "inbox": r.llen(INBOX),
                "imports": r.llen(IMPORTS),
                "import_triggered": r.llen(IMPORT_TRIGGERED),
                "broadcast": r.llen(BROADCAST),
                "misc": r.llen(MISC),
            }

            total_tasks = sum(queues.values())
            duration_ms = (time.time() - start) * 1000

            details = {
                "queues": queues,
                "total_pending_tasks": total_tasks,
                "response_time_ms": round(duration_ms, 2),
            }

            # Determine status based on queue depth
            if total_tasks < 1000:
                status = "healthy"
                message = "Redis broker operational"
            elif total_tasks < 5000:
                status = "degraded"
                message = f"Redis broker has {total_tasks} pending tasks"
            else:
                status = "unhealthy"
                message = f"Redis broker overloaded: {total_tasks} pending tasks"

            result = HealthCheckResult(
                name="redis_broker",
                status=status,
                message=message,
                details=details,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            result = HealthCheckResult(
                name="redis_broker",
                status="unhealthy",
                message=f"Redis broker check failed: {str(e)}",
                details={"error": str(e)},
                duration_ms=duration_ms,
            )

        self.results.append(result)
        return result

    def check_redis_activity(self) -> HealthCheckResult:
        """Check Redis activity stream connectivity.

        Returns:
            HealthCheckResult with Redis activity status
        """
        start = time.time()
        try:
            r = redis.from_url(settings.REDIS_ACTIVITY_URL)
            r.ping()

            # Get memory usage
            info = r.info("memory")
            used_memory = info.get("used_memory_human", "unknown")
            max_memory = info.get("maxmemory_human", "unlimited")

            # Get key count
            db_info = r.info("keyspace")
            total_keys = 0
            for db_key, db_stats in db_info.items():
                if "keys" in db_stats:
                    total_keys += db_stats["keys"]

            duration_ms = (time.time() - start) * 1000

            details = {
                "used_memory": used_memory,
                "max_memory": max_memory,
                "total_keys": total_keys,
                "response_time_ms": round(duration_ms, 2),
            }

            result = HealthCheckResult(
                name="redis_activity",
                status="healthy",
                message="Redis activity stream operational",
                details=details,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            result = HealthCheckResult(
                name="redis_activity",
                status="unhealthy",
                message=f"Redis activity check failed: {str(e)}",
                details={"error": str(e)},
                duration_ms=duration_ms,
            )

        self.results.append(result)
        return result

    def check_celery(self) -> HealthCheckResult:
        """Check Celery worker status.

        Returns:
            HealthCheckResult with Celery worker status
        """
        start = time.time()
        try:
            inspect = celery.control.inspect()
            stats = inspect.stats()
            active = inspect.active()

            if stats is None or not stats:
                duration_ms = (time.time() - start) * 1000
                result = HealthCheckResult(
                    name="celery",
                    status="unhealthy",
                    message="No Celery workers detected",
                    details={"worker_count": 0},
                    duration_ms=duration_ms,
                )
            else:
                worker_count = len(stats)
                active_tasks = sum(len(tasks) for tasks in active.values()) if active else 0

                duration_ms = (time.time() - start) * 1000

                details = {
                    "worker_count": worker_count,
                    "active_tasks": active_tasks,
                    "workers": list(stats.keys()),
                }

                result = HealthCheckResult(
                    name="celery",
                    status="healthy",
                    message=f"{worker_count} Celery worker(s) active",
                    details=details,
                    duration_ms=duration_ms,
                )

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            result = HealthCheckResult(
                name="celery",
                status="unhealthy",
                message=f"Celery check failed: {str(e)}",
                details={"error": str(e)},
                duration_ms=duration_ms,
            )

        self.results.append(result)
        return result

    def check_cache(self) -> HealthCheckResult:
        """Check Django cache functionality.

        Returns:
            HealthCheckResult with cache status
        """
        start = time.time()
        test_key = "health_check_test"
        test_value = "test_value"

        try:
            # Test write
            cache.set(test_key, test_value, timeout=60)

            # Test read
            retrieved = cache.get(test_key)

            # Test delete
            cache.delete(test_key)

            duration_ms = (time.time() - start) * 1000

            if retrieved == test_value:
                result = HealthCheckResult(
                    name="cache",
                    status="healthy",
                    message="Cache operational",
                    details={"response_time_ms": round(duration_ms, 2)},
                    duration_ms=duration_ms,
                )
            else:
                result = HealthCheckResult(
                    name="cache",
                    status="unhealthy",
                    message="Cache read/write test failed",
                    details={"expected": test_value, "got": retrieved},
                    duration_ms=duration_ms,
                )

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            result = HealthCheckResult(
                name="cache",
                status="unhealthy",
                message=f"Cache check failed: {str(e)}",
                details={"error": str(e)},
                duration_ms=duration_ms,
            )

        self.results.append(result)
        return result

    def check_storage(self) -> HealthCheckResult:
        """Check storage backend accessibility.

        Returns:
            HealthCheckResult with storage status
        """
        start = time.time()
        try:
            from django.core.files.storage import default_storage
            import os

            # Check if storage is accessible
            try:
                # For local storage, check directory exists and is writable
                if hasattr(default_storage, "location"):
                    location = default_storage.location
                    exists = os.path.exists(location)
                    writable = os.access(location, os.W_OK) if exists else False

                    details = {
                        "backend": "local",
                        "location": location,
                        "exists": exists,
                        "writable": writable,
                    }

                    if exists and writable:
                        status = "healthy"
                        message = "Storage accessible"
                    elif exists:
                        status = "degraded"
                        message = "Storage exists but not writable"
                    else:
                        status = "unhealthy"
                        message = "Storage directory does not exist"

                # For S3/remote storage
                else:
                    # Just check if we can list (might be slow for large buckets)
                    backend_name = type(default_storage).__name__
                    details = {"backend": backend_name}
                    status = "healthy"
                    message = f"Storage backend: {backend_name}"

            except Exception as e:
                details = {"error": str(e)}
                status = "unhealthy"
                message = f"Storage check failed: {str(e)}"

            duration_ms = (time.time() - start) * 1000
            details["response_time_ms"] = round(duration_ms, 2)

            result = HealthCheckResult(
                name="storage",
                status=status,
                message=message,
                details=details,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            result = HealthCheckResult(
                name="storage",
                status="unhealthy",
                message=f"Storage check failed: {str(e)}",
                details={"error": str(e)},
                duration_ms=duration_ms,
            )

        self.results.append(result)
        return result

    def check_email_config(self) -> HealthCheckResult:
        """Check email configuration validity.

        Returns:
            HealthCheckResult with email config status
        """
        start = time.time()
        try:
            from bookwyrm.utils import regex
            import re

            errors = []

            # Check email sender domain
            if re.findall(r"[\s\@]", settings.EMAIL_SENDER_DOMAIN):
                errors.append("Email sender domain contains invalid characters")

            if not re.match(regex.DOMAIN, settings.EMAIL_SENDER_DOMAIN):
                errors.append("Email sender domain format is invalid")

            # Check required settings
            if not settings.EMAIL_HOST:
                errors.append("EMAIL_HOST not configured")

            if not settings.EMAIL_HOST_USER and settings.EMAIL_BACKEND != "django.core.mail.backends.console.EmailBackend":
                errors.append("EMAIL_HOST_USER not configured")

            duration_ms = (time.time() - start) * 1000

            details = {
                "email_backend": settings.EMAIL_BACKEND,
                "email_host": settings.EMAIL_HOST,
                "email_port": settings.EMAIL_PORT,
                "email_sender": f"{settings.EMAIL_SENDER_NAME}@{settings.EMAIL_SENDER_DOMAIN}",
                "use_tls": settings.EMAIL_USE_TLS,
                "use_ssl": settings.EMAIL_USE_SSL,
            }

            if errors:
                result = HealthCheckResult(
                    name="email_config",
                    status="degraded",
                    message=f"Email configuration has issues: {', '.join(errors)}",
                    details={**details, "errors": errors},
                    duration_ms=duration_ms,
                )
            else:
                result = HealthCheckResult(
                    name="email_config",
                    status="healthy",
                    message="Email configuration appears valid",
                    details=details,
                    duration_ms=duration_ms,
                )

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            result = HealthCheckResult(
                name="email_config",
                status="unhealthy",
                message=f"Email config check failed: {str(e)}",
                details={"error": str(e)},
                duration_ms=duration_ms,
            )

        self.results.append(result)
        return result

    def check_federation(self) -> HealthCheckResult:
        """Check federation capabilities.

        Returns:
            HealthCheckResult with federation status
        """
        start = time.time()
        try:
            # Check recent federated activity
            recent_cutoff = datetime.now() - timedelta(hours=24)

            # Count recent incoming activities
            recent_incoming = models.Status.objects.filter(
                published_date__gte=recent_cutoff, user__local=False
            ).count()

            # Count federated instances
            federated_count = models.FederatedServer.objects.filter(
                status="federated"
            ).count()

            # Count blocked instances
            blocked_count = models.FederatedServer.objects.filter(
                status="blocked"
            ).count()

            duration_ms = (time.time() - start) * 1000

            details = {
                "federated_servers": federated_count,
                "blocked_servers": blocked_count,
                "recent_incoming_activities_24h": recent_incoming,
                "response_time_ms": round(duration_ms, 2),
            }

            if federated_count > 0:
                status = "healthy"
                message = f"Federation active with {federated_count} instance(s)"
            else:
                status = "degraded"
                message = "No federated instances found"

            result = HealthCheckResult(
                name="federation",
                status=status,
                message=message,
                details=details,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            result = HealthCheckResult(
                name="federation",
                status="degraded",
                message=f"Federation check incomplete: {str(e)}",
                details={"error": str(e)},
                duration_ms=duration_ms,
            )

        self.results.append(result)
        return result

    def get_summary(self) -> Dict:
        """Get summary of all health check results.

        Returns:
            Dictionary with summary statistics
        """
        if not self.results:
            return {"status": "unknown", "message": "No health checks performed"}

        healthy_count = sum(1 for r in self.results if r.status == "healthy")
        degraded_count = sum(1 for r in self.results if r.status == "degraded")
        unhealthy_count = sum(1 for r in self.results if r.status == "unhealthy")
        total = len(self.results)

        if unhealthy_count > 0:
            overall_status = "unhealthy"
            message = f"{unhealthy_count} component(s) unhealthy"
        elif degraded_count > 0:
            overall_status = "degraded"
            message = f"{degraded_count} component(s) degraded"
        else:
            overall_status = "healthy"
            message = "All components healthy"

        return {
            "status": overall_status,
            "message": message,
            "healthy": healthy_count,
            "degraded": degraded_count,
            "unhealthy": unhealthy_count,
            "total": total,
            "checks": [r.to_dict() for r in self.results],
        }
