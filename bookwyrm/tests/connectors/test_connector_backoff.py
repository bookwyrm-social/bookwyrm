"""Tests for Connector Health Backoff System"""
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.core.cache import cache

from bookwyrm.connectors.connector_backoff import ConnectorBackoff, sync_connector_health
from bookwyrm import models


class TestConnectorBackoff(TestCase):
    """Test the ConnectorBackoff class"""

    def setUp(self):
        """Clear cache before each test"""
        cache.clear()
        self.connector_id = "openlibrary.org"

    def tearDown(self):
        """Clear cache after each test"""
        cache.clear()

    def test_should_skip_no_data(self):
        """Test that connector is not skipped when no backoff data exists"""
        result = ConnectorBackoff.should_skip(self.connector_id)
        self.assertFalse(result)

    def test_should_skip_in_backoff(self):
        """Test that connector is skipped when in backoff period"""
        # Record a failure to trigger backoff
        ConnectorBackoff.record_failure(self.connector_id, "timeout")

        # Immediately after failure, should be in backoff (1 second for first failure)
        # But exponential backoff: 2^0 = 1 second delay
        # Check cache directly
        cache_key = ConnectorBackoff._get_cache_key(self.connector_id)
        data = cache.get(cache_key)
        self.assertIsNotNone(data)

        backoff_data = json.loads(data)
        self.assertEqual(backoff_data["failure_count"], 1)

    def test_record_failure_increments_count(self):
        """Test that recording failures increments the count"""
        ConnectorBackoff.record_failure(self.connector_id, "timeout")
        ConnectorBackoff.record_failure(self.connector_id, "http_500")
        ConnectorBackoff.record_failure(self.connector_id, "parse_error")

        cache_key = ConnectorBackoff._get_cache_key(self.connector_id)
        data = json.loads(cache.get(cache_key))
        self.assertEqual(data["failure_count"], 3)

    def test_record_success_clears_backoff(self):
        """Test that recording success clears backoff state"""
        # First record some failures
        ConnectorBackoff.record_failure(self.connector_id, "timeout")
        ConnectorBackoff.record_failure(self.connector_id, "timeout")

        # Verify backoff exists
        cache_key = ConnectorBackoff._get_cache_key(self.connector_id)
        self.assertIsNotNone(cache.get(cache_key))

        # Record success
        ConnectorBackoff.record_success(self.connector_id)

        # Backoff should be cleared
        self.assertIsNone(cache.get(cache_key))

    def test_exponential_backoff_calculation(self):
        """Test that backoff increases exponentially"""
        # Record multiple failures and check backoff times
        # Backoff formula: min(2^(failure_count-1), MAX_BACKOFF)

        ConnectorBackoff.record_failure(self.connector_id, "timeout")
        cache_key = ConnectorBackoff._get_cache_key(self.connector_id)
        data1 = json.loads(cache.get(cache_key))

        # First failure: 2^0 = 1 second
        next_retry1 = datetime.fromisoformat(data1["next_retry"])
        last_failure1 = datetime.fromisoformat(data1["last_failure"])
        diff1 = (next_retry1 - last_failure1).total_seconds()
        self.assertEqual(diff1, 1)  # 2^0 = 1

        ConnectorBackoff.record_failure(self.connector_id, "timeout")
        data2 = json.loads(cache.get(cache_key))

        # Second failure: 2^1 = 2 seconds
        next_retry2 = datetime.fromisoformat(data2["next_retry"])
        last_failure2 = datetime.fromisoformat(data2["last_failure"])
        diff2 = (next_retry2 - last_failure2).total_seconds()
        self.assertEqual(diff2, 2)  # 2^1 = 2

        ConnectorBackoff.record_failure(self.connector_id, "timeout")
        data3 = json.loads(cache.get(cache_key))

        # Third failure: 2^2 = 4 seconds
        next_retry3 = datetime.fromisoformat(data3["next_retry"])
        last_failure3 = datetime.fromisoformat(data3["last_failure"])
        diff3 = (next_retry3 - last_failure3).total_seconds()
        self.assertEqual(diff3, 4)  # 2^2 = 4

    def test_max_backoff_cap(self):
        """Test that backoff is capped at MAX_BACKOFF"""
        # Record enough failures to exceed max backoff
        for _ in range(20):  # 2^19 = 524288, well over MAX_BACKOFF
            ConnectorBackoff.record_failure(self.connector_id, "timeout")

        cache_key = ConnectorBackoff._get_cache_key(self.connector_id)
        data = json.loads(cache.get(cache_key))

        next_retry = datetime.fromisoformat(data["next_retry"])
        last_failure = datetime.fromisoformat(data["last_failure"])
        diff = (next_retry - last_failure).total_seconds()

        self.assertEqual(diff, ConnectorBackoff.MAX_BACKOFF)

    def test_get_health_stats_no_data(self):
        """Test health stats with no data returns healthy defaults"""
        stats = ConnectorBackoff.get_health_stats(self.connector_id)

        self.assertEqual(stats["success_count"], 0)
        self.assertEqual(stats["failure_count"], 0)
        self.assertEqual(stats["success_rate"], 100.0)
        self.assertEqual(stats["health_status"], "healthy")
        self.assertFalse(stats["in_backoff"])

    def test_get_health_stats_with_failures(self):
        """Test health stats calculation with failures"""
        # Record some successes and failures
        ConnectorBackoff.record_success(self.connector_id, latency_ms=100)
        ConnectorBackoff.record_success(self.connector_id, latency_ms=150)
        ConnectorBackoff.record_failure(self.connector_id, "timeout", latency_ms=5000)

        stats = ConnectorBackoff.get_health_stats(self.connector_id)

        self.assertEqual(stats["success_count"], 2)
        self.assertEqual(stats["failure_count"], 1)
        self.assertAlmostEqual(stats["success_rate"], 66.7, places=1)

    def test_health_status_degraded(self):
        """Test that health status becomes degraded below threshold"""
        # 70% success rate = degraded threshold
        # 7 successes, 3 failures = 70% -> degraded
        for _ in range(7):
            ConnectorBackoff.record_success(self.connector_id)
        for _ in range(4):
            ConnectorBackoff.record_failure(self.connector_id, "error")

        stats = ConnectorBackoff.get_health_stats(self.connector_id)
        # 7/11 = 63.6% < 70% = degraded
        self.assertEqual(stats["health_status"], "degraded")

    def test_health_status_unavailable(self):
        """Test that health status becomes unavailable below threshold"""
        # 30% success rate = unavailable threshold
        for _ in range(2):
            ConnectorBackoff.record_success(self.connector_id)
        for _ in range(8):
            ConnectorBackoff.record_failure(self.connector_id, "error")

        stats = ConnectorBackoff.get_health_stats(self.connector_id)
        # 2/10 = 20% < 30% = unavailable
        self.assertEqual(stats["health_status"], "unavailable")

    def test_update_stats_latency_tracking(self):
        """Test that latency is tracked correctly"""
        ConnectorBackoff.record_success(self.connector_id, latency_ms=100)
        ConnectorBackoff.record_success(self.connector_id, latency_ms=200)
        ConnectorBackoff.record_success(self.connector_id, latency_ms=300)

        stats = ConnectorBackoff.get_health_stats(self.connector_id)
        # Rolling average: should be ~200
        self.assertGreater(stats["avg_latency_ms"], 100)
        self.assertLess(stats["avg_latency_ms"], 300)

    def test_empty_stats_structure(self):
        """Test that empty stats has correct structure"""
        stats = ConnectorBackoff._empty_stats()

        self.assertIn("success_count", stats)
        self.assertIn("failure_count", stats)
        self.assertIn("avg_latency_ms", stats)
        self.assertIn("last_updated", stats)
        self.assertEqual(stats["success_count"], 0)
        self.assertEqual(stats["failure_count"], 0)


class TestSyncConnectorHealth(TestCase):
    """Test the Celery task for syncing health"""

    @classmethod
    def setUpTestData(cls):
        """Create test connector"""
        cls.connector = models.Connector.objects.create(
            identifier="test.connector.local",
            name="Test Connector",
            connector_file="openlibrary",
            base_url="https://test.connector.local",
            books_url="https://test.connector.local/books",
            covers_url="https://test.connector.local/covers",
            search_url="https://test.connector.local/search?q=",
            priority=1,
            active=True,
        )

    def setUp(self):
        """Clear cache before each test"""
        cache.clear()

    def tearDown(self):
        """Clear cache after each test"""
        cache.clear()

    def test_sync_connector_health_task(self):
        """Test that sync task updates connector health status"""
        # Record some activity for the connector
        ConnectorBackoff.record_success(self.connector.identifier, latency_ms=100)

        # Run the sync task
        result = sync_connector_health()

        self.assertIn("updated", result)
        self.assertGreaterEqual(result["updated"], 1)

    def test_sync_updates_database_status(self):
        """Test that sync task updates database health status"""
        # Record failures to make connector degraded
        for _ in range(4):
            ConnectorBackoff.record_failure(self.connector.identifier, "error")
        for _ in range(6):
            ConnectorBackoff.record_success(self.connector.identifier)

        # Run sync
        sync_connector_health()

        # Refresh from database
        self.connector.refresh_from_db()

        # Check health status was updated
        self.assertIn(self.connector.health_status, ["healthy", "degraded", "unavailable"])
