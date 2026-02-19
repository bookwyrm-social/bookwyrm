"""Query profiling middleware for Django.

This middleware profiles database queries for each request and logs
performance warnings for slow queries and N+1 query patterns.
"""

import logging
import time
from django.conf import settings
from django.db import connection, reset_queries

from bookwyrm.utils.performance import QueryProfiler

logger = logging.getLogger(__name__)


class QueryProfilingMiddleware:
    """Middleware to profile database queries for each request."""

    def __init__(self, get_response):
        """Initialize middleware.

        Args:
            get_response: Next middleware or view
        """
        self.get_response = get_response
        self.enabled = getattr(settings, "ENABLE_QUERY_PROFILING", settings.DEBUG)
        self.log_threshold_ms = getattr(settings, "QUERY_PROFILE_THRESHOLD_MS", 1000)
        self.query_count_threshold = getattr(settings, "QUERY_COUNT_THRESHOLD", 50)

    def __call__(self, request):
        """Process request and profile queries.

        Args:
            request: Django request object

        Returns:
            Response object
        """
        if not self.enabled:
            return self.get_response(request)

        # Reset queries before processing request
        reset_queries()
        start_time = time.time()

        # Create profiler
        profiler = QueryProfiler()
        profiler.start()

        # Process request
        response = self.get_response(request)

        # Stop profiling and analyze
        profiler.stop()
        summary = profiler.get_summary()

        # Calculate total request time
        duration_ms = (time.time() - start_time) * 1000

        # Add profiling headers to response (if DEBUG)
        if settings.DEBUG:
            response["X-Query-Count"] = str(summary["query_count"])
            response["X-Query-Time-Ms"] = str(summary["total_time_ms"])
            response["X-Total-Time-Ms"] = str(round(duration_ms, 2))

        # Log warnings for slow requests
        if duration_ms > self.log_threshold_ms:
            logger.warning(
                f"Slow request: {request.path} took {duration_ms:.2f}ms "
                f"with {summary['query_count']} queries "
                f"(query time: {summary['total_time_ms']:.2f}ms)"
            )

        # Log warnings for requests with many queries
        if summary["query_count"] > self.query_count_threshold:
            logger.warning(
                f"Request with many queries: {request.path} "
                f"executed {summary['query_count']} queries "
                f"in {summary['total_time_ms']:.2f}ms"
            )

        # Log N+1 query warnings
        if summary["n_plus_one_detected"]:
            for n_plus_one in summary["n_plus_one_detected"]:
                logger.warning(
                    f"Possible N+1 query detected in {request.path}: "
                    f"Query executed {n_plus_one['count']} times, "
                    f"total time: {n_plus_one['total_time']:.4f}s. "
                    f"Pattern: {n_plus_one['pattern']}"
                )

        return response


class PerformanceLoggingMiddleware:
    """Middleware to log detailed performance metrics."""

    def __init__(self, get_response):
        """Initialize middleware.

        Args:
            get_response: Next middleware or view
        """
        self.get_response = get_response
        self.enabled = getattr(settings, "ENABLE_PERFORMANCE_LOGGING", False)

    def __call__(self, request):
        """Process request and log performance.

        Args:
            request: Django request object

        Returns:
            Response object
        """
        if not self.enabled:
            return self.get_response(request)

        start_time = time.time()
        reset_queries()

        # Process request
        response = self.get_response(request)

        # Calculate metrics
        duration_ms = (time.time() - start_time) * 1000
        query_count = len(connection.queries)
        query_time_ms = sum(float(q["time"]) for q in connection.queries) * 1000

        # Log performance data
        logger.info(
            f"Performance [{request.method} {request.path}]: "
            f"total={duration_ms:.2f}ms, "
            f"queries={query_count}, "
            f"query_time={query_time_ms:.2f}ms, "
            f"status={response.status_code}"
        )

        return response
