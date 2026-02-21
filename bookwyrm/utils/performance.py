"""Performance profiling utilities for BookWyrm.

Provides tools for profiling query performance, detecting N+1 queries,
tracking view performance, and identifying performance bottlenecks.
"""

import functools
import logging
import time
from collections import defaultdict
from contextlib import contextmanager
from typing import Any, Callable, Dict, List, Optional

from django.conf import settings
from django.core.cache import cache
from django.db import connection, reset_queries

logger = logging.getLogger(__name__)


class QueryProfiler:
    """Profiles database queries and detects performance issues."""

    def __init__(self):
        """Initialize the query profiler."""
        self.queries: List[Dict] = []
        self.query_counts: Dict[str, int] = defaultdict(int)
        self.total_time: float = 0.0
        self.n_plus_one_detected: List[str] = []

    def start(self):
        """Start profiling queries."""
        reset_queries()
        self.queries = []
        self.query_counts = defaultdict(int)
        self.total_time = 0.0
        self.n_plus_one_detected = []

    def stop(self) -> Dict:
        """Stop profiling and analyze results.

        Returns:
            Dictionary with profiling results
        """
        queries = connection.queries
        self.queries = queries
        self.total_time = sum(float(q["time"]) for q in queries)

        # Analyze query patterns
        self._analyze_queries()

        return self.get_summary()

    def _analyze_queries(self):
        """Analyze queries for patterns and issues."""
        # Group similar queries
        query_patterns = defaultdict(list)

        for query in self.queries:
            # Normalize query by removing specific values
            normalized = self._normalize_query(query["sql"])
            query_patterns[normalized].append(query)
            self.query_counts[normalized] += 1

        # Detect potential N+1 queries (same query executed many times)
        for pattern, queries in query_patterns.items():
            if len(queries) > 5:  # Threshold for N+1 detection
                self.n_plus_one_detected.append({
                    "pattern": pattern[:200],
                    "count": len(queries),
                    "total_time": sum(float(q["time"]) for q in queries),
                })

    def _normalize_query(self, sql: str) -> str:
        """Normalize SQL query for pattern matching.

        Args:
            sql: SQL query string

        Returns:
            Normalized query string
        """
        import re

        # Remove specific IDs and values
        normalized = re.sub(r"\b\d+\b", "?", sql)
        # Remove string literals
        normalized = re.sub(r"'[^']*'", "?", normalized)
        # Remove IN clauses with multiple values
        normalized = re.sub(r"IN \([^)]+\)", "IN (?)", normalized)

        return normalized

    def get_summary(self) -> Dict:
        """Get profiling summary.

        Returns:
            Dictionary with profiling statistics
        """
        if not self.queries:
            return {
                "query_count": 0,
                "total_time_ms": 0.0,
                "n_plus_one_detected": [],
                "slowest_queries": [],
            }

        # Find slowest queries
        slowest = sorted(
            self.queries, key=lambda q: float(q["time"]), reverse=True
        )[:10]

        return {
            "query_count": len(self.queries),
            "total_time_ms": round(self.total_time * 1000, 2),
            "average_time_ms": round((self.total_time / len(self.queries)) * 1000, 2) if self.queries else 0,
            "n_plus_one_detected": self.n_plus_one_detected,
            "slowest_queries": [
                {
                    "sql": q["sql"][:200],
                    "time_ms": round(float(q["time"]) * 1000, 2),
                }
                for q in slowest
            ],
        }


@contextmanager
def profile_queries():
    """Context manager for profiling queries.

    Usage:
        with profile_queries() as profiler:
            # Your code here
            pass
        print(profiler.get_summary())

    Yields:
        QueryProfiler instance
    """
    if not settings.DEBUG:
        # Only profile in debug mode
        profiler = QueryProfiler()
        yield profiler
        return

    profiler = QueryProfiler()
    profiler.start()
    try:
        yield profiler
    finally:
        profiler.stop()


class ViewPerformanceTracker:
    """Tracks view performance metrics."""

    CACHE_KEY_PREFIX = "view_perf"
    CACHE_TIMEOUT = 3600  # 1 hour

    @classmethod
    def record(cls, view_name: str, duration_ms: float, query_count: int):
        """Record view performance metrics.

        Args:
            view_name: Name of the view
            duration_ms: Total duration in milliseconds
            query_count: Number of queries executed
        """
        cache_key = f"{cls.CACHE_KEY_PREFIX}:{view_name}"
        data = cache.get(cache_key, {
            "view_name": view_name,
            "total_calls": 0,
            "total_time_ms": 0.0,
            "total_queries": 0,
            "min_time_ms": float("inf"),
            "max_time_ms": 0.0,
        })

        data["total_calls"] += 1
        data["total_time_ms"] += duration_ms
        data["total_queries"] += query_count
        data["min_time_ms"] = min(data["min_time_ms"], duration_ms)
        data["max_time_ms"] = max(data["max_time_ms"], duration_ms)
        data["avg_time_ms"] = data["total_time_ms"] / data["total_calls"]
        data["avg_queries"] = data["total_queries"] / data["total_calls"]

        cache.set(cache_key, data, cls.CACHE_TIMEOUT)

    @classmethod
    def get_stats(cls, view_name: str) -> Optional[Dict]:
        """Get performance statistics for a view.

        Args:
            view_name: Name of the view

        Returns:
            Performance statistics or None if not tracked
        """
        cache_key = f"{cls.CACHE_KEY_PREFIX}:{view_name}"
        return cache.get(cache_key)

    @classmethod
    def get_all_stats(cls) -> List[Dict]:
        """Get performance statistics for all tracked views.

        Returns:
            List of performance statistics
        """
        # Note: This requires iterating over cache keys, which may not be
        # supported by all cache backends. For production, consider using
        # a database table or structured logging.
        # This is a simplified implementation.
        return []


def profile_view(view_func: Callable) -> Callable:
    """Decorator to profile view performance.

    Usage:
        @profile_view
        def my_view(request):
            # View code
            pass

    Args:
        view_func: View function to profile

    Returns:
        Wrapped view function
    """
    @functools.wraps(view_func)
    def wrapper(*args, **kwargs):
        if not settings.DEBUG:
            # Don't profile in production
            return view_func(*args, **kwargs)

        start_time = time.time()
        reset_queries()

        try:
            result = view_func(*args, **kwargs)
            return result
        finally:
            duration_ms = (time.time() - start_time) * 1000
            query_count = len(connection.queries)

            view_name = f"{view_func.__module__}.{view_func.__name__}"
            ViewPerformanceTracker.record(view_name, duration_ms, query_count)

            # Log if slow
            if duration_ms > 1000:  # 1 second
                logger.warning(
                    f"Slow view: {view_name} took {duration_ms:.2f}ms "
                    f"with {query_count} queries"
                )

            # Log if many queries
            if query_count > 50:
                logger.warning(
                    f"View with many queries: {view_name} executed {query_count} queries"
                )

    return wrapper


class PerformanceMonitor:
    """Monitors and reports on application performance."""

    def __init__(self):
        """Initialize the performance monitor."""
        self.metrics: Dict[str, List[float]] = defaultdict(list)

    def record_metric(self, name: str, value: float):
        """Record a performance metric.

        Args:
            name: Metric name
            value: Metric value
        """
        self.metrics[name].append(value)

    def get_stats(self, name: str) -> Optional[Dict]:
        """Get statistics for a metric.

        Args:
            name: Metric name

        Returns:
            Dictionary with statistics or None if metric not found
        """
        if name not in self.metrics or not self.metrics[name]:
            return None

        values = self.metrics[name]
        count = len(values)
        total = sum(values)
        avg = total / count
        min_val = min(values)
        max_val = max(values)

        # Calculate percentiles
        sorted_values = sorted(values)
        p50 = sorted_values[int(count * 0.5)]
        p95 = sorted_values[int(count * 0.95)] if count > 1 else max_val
        p99 = sorted_values[int(count * 0.99)] if count > 1 else max_val

        return {
            "count": count,
            "total": round(total, 2),
            "average": round(avg, 2),
            "min": round(min_val, 2),
            "max": round(max_val, 2),
            "p50": round(p50, 2),
            "p95": round(p95, 2),
            "p99": round(p99, 2),
        }

    def get_all_stats(self) -> Dict[str, Dict]:
        """Get statistics for all metrics.

        Returns:
            Dictionary mapping metric names to their statistics
        """
        return {name: self.get_stats(name) for name in self.metrics}


@contextmanager
def measure_performance(metric_name: str, monitor: Optional[PerformanceMonitor] = None):
    """Context manager for measuring performance.

    Usage:
        monitor = PerformanceMonitor()
        with measure_performance("my_operation", monitor):
            # Code to measure
            pass

    Args:
        metric_name: Name of the metric
        monitor: PerformanceMonitor instance (optional)

    Yields:
        None
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = (time.time() - start_time) * 1000  # Convert to ms
        if monitor:
            monitor.record_metric(metric_name, duration)
        logger.debug(f"Performance: {metric_name} took {duration:.2f}ms")


def detect_select_related_opportunities() -> List[Dict]:
    """Analyze recent queries to detect opportunities for select_related/prefetch_related.

    Returns:
        List of optimization opportunities
    """
    if not settings.DEBUG:
        return []

    queries = connection.queries
    opportunities = []

    # Simple pattern detection for related object access
    join_pattern_count = defaultdict(int)

    for query in queries:
        sql = query["sql"].upper()
        # Detect queries without JOINs that might benefit from them
        if "JOIN" not in sql and "WHERE" in sql and '"ID"' in sql:
            # This is a simplistic check - in production, would need more sophisticated analysis
            join_pattern_count[sql[:100]] += 1

    # Flag patterns that appear frequently
    for pattern, count in join_pattern_count.items():
        if count > 3:
            opportunities.append({
                "pattern": pattern,
                "occurrences": count,
                "suggestion": "Consider using select_related() or prefetch_related()",
            })

    return opportunities


def analyze_query_performance(min_duration_ms: float = 100.0) -> Dict:
    """Analyze query performance from recent queries.

    Args:
        min_duration_ms: Minimum duration to consider a query slow

    Returns:
        Dictionary with analysis results
    """
    if not settings.DEBUG:
        return {"error": "Query analysis only available in DEBUG mode"}

    queries = connection.queries
    slow_queries = []
    query_distribution = defaultdict(int)

    for query in queries:
        duration_ms = float(query["time"]) * 1000

        # Record query type distribution
        sql = query["sql"].strip().split()[0].upper()
        query_distribution[sql] += 1

        # Identify slow queries
        if duration_ms >= min_duration_ms:
            slow_queries.append({
                "sql": query["sql"][:200],
                "duration_ms": round(duration_ms, 2),
            })

    return {
        "total_queries": len(queries),
        "slow_query_count": len(slow_queries),
        "slow_queries": sorted(
            slow_queries, key=lambda q: q["duration_ms"], reverse=True
        )[:10],
        "query_distribution": dict(query_distribution),
        "select_related_opportunities": detect_select_related_opportunities(),
    }
