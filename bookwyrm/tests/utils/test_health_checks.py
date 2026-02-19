"""Tests for health check utilities"""

from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.cache import cache
from django.core.files.storage import default_storage
from bookwyrm.utils.health_checks import HealthCheckResult, HealthChecker


class HealthCheckResultTest(TestCase):
    """Test HealthCheckResult class"""

    def test_init_healthy(self):
        """Initialize a healthy check result"""
        result = HealthCheckResult("test_check", "healthy", "All good")
        self.assertEqual(result.check_name, "test_check")
        self.assertEqual(result.status, "healthy")
        self.assertEqual(result.message, "All good")
        self.assertIsNone(result.details)

    def test_init_unhealthy_with_details(self):
        """Initialize an unhealthy result with details"""
        details = {"error": "Connection refused"}
        result = HealthCheckResult("test_check", "unhealthy", "Failed", details)
        self.assertEqual(result.status, "unhealthy")
        self.assertEqual(result.details, details)

    def test_to_dict(self):
        """Convert result to dictionary"""
        result = HealthCheckResult("test_check", "degraded", "Slow", {"latency": 500})
        result_dict = result.to_dict()
        
        self.assertEqual(result_dict["check_name"], "test_check")
        self.assertEqual(result_dict["status"], "degraded")
        self.assertEqual(result_dict["message"], "Slow")
        self.assertEqual(result_dict["details"]["latency"], 500)
        self.assertIn("timestamp", result_dict)

    def test_is_healthy(self):
        """Test healthy status check"""
        healthy = HealthCheckResult("test", "healthy", "OK")
        degraded = HealthCheckResult("test", "degraded", "Slow")
        unhealthy = HealthCheckResult("test", "unhealthy", "Failed")
        
        self.assertTrue(healthy.is_healthy())
        self.assertFalse(degraded.is_healthy())
        self.assertFalse(unhealthy.is_healthy())


class HealthCheckerDatabaseTest(TestCase):
    """Test database health checks"""

    def setUp(self):
        """Set up test fixtures"""
        self.checker = HealthChecker()

    @patch("bookwyrm.utils.health_checks.connection")
    def test_check_database_healthy(self, mock_connection):
        """Database check succeeds"""
        mock_cursor = MagicMock()
        mock_cursor.execute.return_value = None
        mock_cursor.fetchone.return_value = (1,)
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connection.queries = []

        result = self.checker.check_database()
        
        self.assertEqual(result.status, "healthy")
        self.assertIn("Database connection successful", result.message)

    @patch("bookwyrm.utils.health_checks.connection")
    def test_check_database_slow(self, mock_connection):
        """Database check detects slow response"""
        mock_cursor = MagicMock()
        mock_cursor.execute.return_value = None
        mock_cursor.fetchone.return_value = (1,)
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connection.queries = []
        
        # Simulate slow response
        with patch("bookwyrm.utils.health_checks.time.time", side_effect=[0, 2.5]):
            result = self.checker.check_database()
        
        self.assertEqual(result.status, "degraded")
        self.assertIn("slow", result.message.lower())

    @patch("bookwyrm.utils.health_checks.connection")
    def test_check_database_connection_error(self, mock_connection):
        """Database check handles connection failure"""
        mock_connection.cursor.side_effect = Exception("Connection refused")

        result = self.checker.check_database()
        
        self.assertEqual(result.status, "unhealthy")
        self.assertIn("Connection refused", result.message)

    @patch("bookwyrm.utils.health_checks.connection")
    def test_check_database_connection_pool(self, mock_connection):
        """Database check reports connection pool stats"""
        mock_cursor = MagicMock()
        mock_cursor.execute.return_value = None
        mock_cursor.fetchone.return_value = (1,)
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connection.queries = []

        result = self.checker.check_database()
        
        self.assertIsNotNone(result.details)


class HealthCheckerRedisTest(TestCase):
    """Test Redis health checks"""

    def setUp(self):
        """Set up test fixtures"""
        self.checker = HealthChecker()

    @patch("bookwyrm.utils.health_checks.redis")
    @patch("bookwyrm.utils.health_checks.settings")
    def test_check_redis_broker_healthy(self, mock_settings, mock_redis):
        """Redis broker check succeeds"""
        mock_settings.REDIS_BROKER_URL = "redis://localhost:6379/0"
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.info.return_value = {
            "used_memory_human": "10M",
            "connected_clients": 5,
        }
        mock_redis.from_url.return_value = mock_client

        result = self.checker.check_redis_broker()
        
        self.assertEqual(result.status, "healthy")
        self.assertIn("Redis broker", result.message)

    @patch("bookwyrm.utils.health_checks.redis")
    @patch("bookwyrm.utils.health_checks.settings")
    def test_check_redis_broker_unavailable(self, mock_settings, mock_redis):
        """Redis broker check handles connection failure"""
        mock_settings.REDIS_BROKER_URL = "redis://localhost:6379/0"
        mock_client = MagicMock()
        mock_client.ping.side_effect = Exception("Connection refused")
        mock_redis.from_url.return_value = mock_client

        result = self.checker.check_redis_broker()
        
        self.assertEqual(result.status, "unhealthy")
        self.assertIn("Connection refused", result.message)

    @patch("bookwyrm.utils.health_checks.redis")
    @patch("bookwyrm.utils.health_checks.settings")
    def test_check_redis_activity_healthy(self, mock_settings, mock_redis):
        """Redis activity check succeeds"""
        mock_settings.REDIS_ACTIVITY_URL = "redis://localhost:6379/1"
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.info.return_value = {
            "used_memory_human": "50M",
            "connected_clients": 10,
        }
        mock_client.dbsize.return_value = 1000
        mock_redis.from_url.return_value = mock_client

        result = self.checker.check_redis_activity()
        
        self.assertEqual(result.status, "healthy")
        self.assertEqual(result.details["key_count"], 1000)


class HealthCheckerCeleryTest(TestCase):
    """Test Celery health checks"""

    def setUp(self):
        """Set up test fixtures"""
        self.checker = HealthChecker()

    @patch("bookwyrm.utils.health_checks.celery_app")
    def test_check_celery_workers_active(self, mock_celery_app):
        """Celery check finds active workers"""
        mock_celery_app.control.inspect.return_value.active.return_value = {
            "celery@worker1": [{"name": "task1"}],
            "celery@worker2": [],
        }
        mock_celery_app.control.inspect.return_value.stats.return_value = {
            "celery@worker1": {"pool": {"max-concurrency": 4}},
            "celery@worker2": {"pool": {"max-concurrency": 4}},
        }

        result = self.checker.check_celery()
        
        self.assertEqual(result.status, "healthy")
        self.assertEqual(result.details["worker_count"], 2)
        self.assertEqual(result.details["active_tasks"], 1)

    @patch("bookwyrm.utils.health_checks.celery_app")
    def test_check_celery_no_workers(self, mock_celery_app):
        """Celery check detects no workers"""
        mock_celery_app.control.inspect.return_value.active.return_value = None
        mock_celery_app.control.inspect.return_value.stats.return_value = None

        result = self.checker.check_celery()
        
        self.assertEqual(result.status, "unhealthy")
        self.assertIn("No workers", result.message)

    @patch("bookwyrm.utils.health_checks.celery_app")
    def test_check_celery_error(self, mock_celery_app):
        """Celery check handles errors"""
        mock_celery_app.control.inspect.return_value.active.side_effect = Exception("Timeout")

        result = self.checker.check_celery()
        
        self.assertEqual(result.status, "unhealthy")
        self.assertIn("Timeout", result.message)


class HealthCheckerCacheTest(TestCase):
    """Test cache health checks"""

    def setUp(self):
        """Set up test fixtures"""
        self.checker = HealthChecker()
        # Clear cache before each test
        cache.clear()

    def test_check_cache_healthy(self):
        """Cache check succeeds with read/write/delete"""
        result = self.checker.check_cache()
        
        self.assertEqual(result.status, "healthy")
        self.assertIn("operational", result.message)

    @patch("bookwyrm.utils.health_checks.cache")
    def test_check_cache_write_failure(self, mock_cache):
        """Cache check detects write failure"""
        mock_cache.set.return_value = False

        result = self.checker.check_cache()
        
        self.assertEqual(result.status, "unhealthy")
        self.assertIn("Failed to write", result.message)

    @patch("bookwyrm.utils.health_checks.cache")
    def test_check_cache_read_failure(self, mock_cache):
        """Cache check detects read failure"""
        mock_cache.set.return_value = True
        mock_cache.get.return_value = None

        result = self.checker.check_cache()
        
        self.assertEqual(result.status, "unhealthy")
        self.assertIn("Failed to read", result.message)

    @patch("bookwyrm.utils.health_checks.cache")
    def test_check_cache_error(self, mock_cache):
        """Cache check handles errors"""
        mock_cache.set.side_effect = Exception("Connection refused")

        result = self.checker.check_cache()
        
        self.assertEqual(result.status, "unhealthy")
        self.assertIn("Connection refused", result.message)


class HealthCheckerStorageTest(TestCase):
    """Test storage health checks"""

    def setUp(self):
        """Set up test fixtures"""
        self.checker = HealthChecker()

    @patch("bookwyrm.utils.health_checks.default_storage")
    def test_check_storage_healthy(self, mock_storage):
        """Storage check succeeds"""
        mock_storage.save.return_value = "test_file.txt"
        mock_storage.open.return_value. __enter__.return_value.read.return_value = b"test"
        mock_storage.exists.return_value = True
        mock_storage.delete.return_value = None
        mock_storage.get_accessed_time.return_value = 123456789
        mock_storage.size.return_value = 4

        result = self.checker.check_storage()
        
        self.assertEqual(result.status, "healthy")
        self.assertIn("accessible", result.message)

    @patch("bookwyrm.utils.health_checks.default_storage")
    def test_check_storage_write_failure(self, mock_storage):
        """Storage check detects write failure"""
        mock_storage.save.side_effect = Exception("Permission denied")

        result = self.checker.check_storage()
        
        self.assertEqual(result.status, "unhealthy")
        self.assertIn("Permission denied", result.message)


class HealthCheckerEmailTest(TestCase):
    """Test email configuration checks"""

    def setUp(self):
        """Set up test fixtures"""
        self.checker = HealthChecker()

    @patch("bookwyrm.utils.health_checks.settings")
    def test_check_email_config_configured(self, mock_settings):
        """Email check detects configuration"""
        mock_settings.EMAIL_HOST = "smtp.example.com"
        mock_settings.EMAIL_PORT = 587
        mock_settings.DEFAULT_FROM_EMAIL = "noreply@example.com"

        result = self.checker.check_email_config()
        
        self.assertEqual(result.status, "healthy")
        self.assertIn("configured", result.message)

    @patch("bookwyrm.utils.health_checks.settings")
    def test_check_email_config_not_configured(self, mock_settings):
        """Email check detects missing configuration"""
        mock_settings.EMAIL_HOST = ""
        mock_settings.EMAIL_PORT = 25
        mock_settings.DEFAULT_FROM_EMAIL = "webmaster@localhost"

        result = self.checker.check_email_config()
        
        self.assertEqual(result.status, "degraded")
        self.assertIn("not configured", result.message)


class HealthCheckerFederationTest(TestCase):
    """Test federation health checks"""

    def setUp(self):
        """Set up test fixtures"""
        self.checker = HealthChecker()

    @patch("bookwyrm.utils.health_checks.settings")
    def test_check_federation_enabled(self, mock_settings):
        """Federation check detects enabled state"""
        mock_settings.ENABLE_PREVIEW_IMAGES = True
        mock_settings.USE_HTTPS = True
        mock_settings.DOMAIN = "bookwyrm.social"

        result = self.checker.check_federation()
        
        self.assertEqual(result.status, "healthy")
        self.assertIn("operational", result.message)

    @patch("bookwyrm.utils.health_checks.settings")
    def test_check_federation_no_https(self, mock_settings):
        """Federation check warns about missing HTTPS"""
        mock_settings.ENABLE_PREVIEW_IMAGES = True
        mock_settings.USE_HTTPS = False
        mock_settings.DOMAIN = "bookwyrm.local"

        result = self.checker.check_federation()
        
        self.assertEqual(result.status, "degraded")
        self.assertIn("HTTPS not enabled", result.message)


class HealthCheckerFullSuiteTest(TestCase):
    """Test running full health check suite"""

    def setUp(self):
        """Set up test fixtures"""
        self.checker = HealthChecker()

    @patch("bookwyrm.utils.health_checks.HealthChecker.check_database")
    @patch("bookwyrm.utils.health_checks.HealthChecker.check_redis_broker")
    @patch("bookwyrm.utils.health_checks.HealthChecker.check_redis_activity")
    @patch("bookwyrm.utils.health_checks.HealthChecker.check_celery")
    @patch("bookwyrm.utils.health_checks.HealthChecker.check_cache")
    @patch("bookwyrm.utils.health_checks.HealthChecker.check_storage")
    @patch("bookwyrm.utils.health_checks.HealthChecker.check_email_config")
    @patch("bookwyrm.utils.health_checks.HealthChecker.check_federation")
    def test_run_all_checks(
        self,
        mock_federation,
        mock_email,
        mock_storage,
        mock_cache,
        mock_celery,
        mock_redis_activity,
        mock_redis_broker,
        mock_database,
    ):
        """Run all health checks"""
        # Mock all checks as healthy
        for mock_check in [
            mock_database,
            mock_redis_broker,
            mock_redis_activity,
            mock_celery,
            mock_cache,
            mock_storage,
            mock_email,
            mock_federation,
        ]:
            mock_check.return_value = HealthCheckResult(
                "test", "healthy", "OK"
            )

        results = self.checker.run_all_checks()
        
        self.assertEqual(len(results), 8)
        for result in results:
            self.assertEqual(result.status, "healthy")

    @patch("bookwyrm.utils.health_checks.HealthChecker.check_database")
    @patch("bookwyrm.utils.health_checks.HealthChecker.check_redis_broker")
    def test_run_specific_checks(self, mock_redis, mock_database):
        """Run specific health checks"""
        mock_database.return_value = HealthCheckResult("database", "healthy", "OK")
        mock_redis.return_value = HealthCheckResult("redis_broker", "healthy", "OK")

        results = self.checker.run_checks(["database", "redis_broker"])
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].check_name, "database")
        self.assertEqual(results[1].check_name, "redis_broker")

    def test_run_invalid_check_name(self):
        """Handle invalid check names"""
        results = self.checker.run_checks(["invalid_check"])
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "unhealthy")
        self.assertIn("Unknown check", results[0].message)
