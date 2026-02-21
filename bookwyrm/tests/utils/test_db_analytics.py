"""Tests for database analytics utilities"""

from unittest.mock import patch, MagicMock
from django.test import TestCase
from bookwyrm.utils.db_analytics import DatabaseAnalyzer


class DatabaseAnalyzerConnectionStatsTest(TestCase):
    """Test connection statistics"""

    def setUp(self):
        """Set up test fixtures"""
        self.analyzer = DatabaseAnalyzer()

    @patch("bookwyrm.utils.db_analytics.connection")
    def test_get_connection_stats(self, mock_connection):
        """Get database connection statistics"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (10, 5, 100)
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        stats = self.analyzer.get_connection_stats()
        
        self.assertEqual(stats["active_connections"], 10)
        self.assertEqual(stats["idle_connections"], 5)
        self.assertEqual(stats["max_connections"], 100)
        self.assertEqual(stats["total_used"], 15)
        self.assertEqual(stats["usage_percentage"], 15.0)

    @patch("bookwyrm.utils.db_analytics.connection")
    def test_get_connection_stats_error(self, mock_connection):
        """Handle connection stats errors"""
        mock_connection.cursor.side_effect = Exception("Database unavailable")

        stats = self.analyzer.get_connection_stats()
        
        self.assertIn("error", stats)
        self.assertIn("Database unavailable", stats["error"])


class DatabaseAnalyzerSizeStatsTest(TestCase):
    """Test database size statistics"""

    def setUp(self):
        """Set up test fixtures"""
        self.analyzer = DatabaseAnalyzer()

    @patch("bookwyrm.utils.db_analytics.connection")
    def test_get_database_size_stats(self, mock_connection):
        """Get database size statistics"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("bookwyrm", "500 MB")
        mock_cursor.fetchall.return_value = [
            ("bookwyrm_status", "200 MB"),
            ("bookwyrm_review", "100 MB"),
            ("bookwyrm_user", "50 MB"),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        stats = self.analyzer.get_database_size_stats()
        
        self.assertEqual(stats["database_name"], "bookwyrm")
        self.assertEqual(stats["total_size"], "500 MB")
        self.assertEqual(len(stats["largest_tables"]), 3)
        self.assertEqual(stats["largest_tables"][0]["table_name"], "bookwyrm_status")


class DatabaseAnalyzerTableStatsTest(TestCase):
    """Test table statistics"""

    def setUp(self):
        """Set up test fixtures"""
        self.analyzer = DatabaseAnalyzer()

    @patch("bookwyrm.utils.db_analytics.connection")
    def test_get_table_statistics(self, mock_connection):
        """Get table statistics"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("bookwyrm_status", 10000, 500, 200, 5.0, "50 MB", 95.5),
            ("bookwyrm_review", 5000, 100, 50, 2.0, "25 MB", 98.0),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        stats = self.analyzer.get_table_statistics()
        
        self.assertEqual(len(stats), 2)
        self.assertEqual(stats[0]["table_name"], "bookwyrm_status")
        self.assertEqual(stats[0]["live_rows"], 10000)
        self.assertEqual(stats[0]["dead_rows"], 500)
        self.assertEqual(stats[0]["bloat_percentage"], 5.0)

    @patch("bookwyrm.utils.db_analytics.connection")
    def test_get_table_statistics_with_limit(self, mock_connection):
        """Get table statistics with limit"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("bookwyrm_status", 10000, 500, 200, 5.0, "50 MB", 95.5),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        stats = self.analyzer.get_table_statistics(limit=1)
        
        self.assertEqual(len(stats), 1)


class DatabaseAnalyzerIndexStatsTest(TestCase):
    """Test index statistics"""

    def setUp(self):
        """Set up test fixtures"""
        self.analyzer = DatabaseAnalyzer()

    @patch("bookwyrm.utils.db_analytics.connection")
    def test_get_index_statistics(self, mock_connection):
        """Get index statistics"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("idx_status_user", "bookwyrm_status", "10 MB", 50000, 1000),
            ("idx_status_published", "bookwyrm_status", "8 MB", 30000, 500),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        stats = self.analyzer.get_index_statistics()
        
        self.assertEqual(len(stats), 2)
        self.assertEqual(stats[0]["index_name"], "idx_status_user")
        self.assertEqual(stats[0]["scans"], 50000)
        self.assertEqual(stats[0]["tuples_read"], 1000)

    @patch("bookwyrm.utils.db_analytics.connection")
    def test_find_unused_indexes(self, mock_connection):
        """Find unused indexes"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("idx_old_unused", "bookwyrm_status", "15 MB", 0),
            ("idx_rarely_used", "bookwyrm_review", "5 MB", 10),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        indexes = self.analyzer.find_unused_indexes()
        
        self.assertEqual(len(indexes), 2)
        self.assertEqual(indexes[0]["index_name"], "idx_old_unused")
        self.assertEqual(indexes[0]["scans"], 0)


class DatabaseAnalyzerQueryPerformanceTest(TestCase):
    """Test query performance analysis"""

    def setUp(self):
        """Set up test fixtures"""
        self.analyzer = DatabaseAnalyzer()

    @patch("bookwyrm.utils.db_analytics.connection")
    def test_get_query_performance_stats(self, mock_connection):
        """Get query performance statistics"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (True,)  # pg_stat_statements enabled
        mock_cursor.fetchall.return_value = [
            (
                "SELECT * FROM bookwyrm_status WHERE user_id = ?",
                1000,
                5000.0,
                5.0,
                10.0,
            ),
            ("UPDATE bookwyrm_user SET last_login = ?", 500, 2500.0, 5.0, 8.0),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        stats = self.analyzer.get_query_performance_stats()
        
        self.assertTrue(stats["pg_stat_statements_enabled"])
        self.assertEqual(len(stats["slow_queries"]), 2)
        self.assertEqual(stats["slow_queries"][0]["calls"], 1000)

    @patch("bookwyrm.utils.db_analytics.connection")
    def test_get_query_performance_not_enabled(self, mock_connection):
        """Handle pg_stat_statements not enabled"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (False,)
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        stats = self.analyzer.get_query_performance_stats()
        
        self.assertFalse(stats["pg_stat_statements_enabled"])
        self.assertEqual(len(stats["slow_queries"]), 0)


class DatabaseAnalyzerBloatDetectionTest(TestCase):
    """Test table bloat detection"""

    def setUp(self):
        """Set up test fixtures"""
        self.analyzer = DatabaseAnalyzer()

    @patch("bookwyrm.utils.db_analytics.connection")
    def test_detect_bloat(self, mock_connection):
        """Detect bloated tables"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("bookwyrm_status", 10000, 3000, 30.0),
            ("bookwyrm_review", 5000, 1500, 30.0),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        bloated = self.analyzer.detect_bloat()
        
        self.assertEqual(len(bloated), 2)
        self.assertEqual(bloated[0]["table_name"], "bookwyrm_status")
        self.assertEqual(bloated[0]["bloat_percentage"], 30.0)

    @patch("bookwyrm.utils.db_analytics.connection")
    def test_detect_bloat_with_threshold(self, mock_connection):
        """Detect bloat with custom threshold"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("bookwyrm_status", 10000, 5000, 50.0),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        bloated = self.analyzer.detect_bloat(threshold_percentage=40.0)
        
        self.assertEqual(len(bloated), 1)


class DatabaseAnalyzerCacheHitRatioTest(TestCase):
    """Test cache hit ratio analysis"""

    def setUp(self):
        """Set up test fixtures"""
        self.analyzer = DatabaseAnalyzer()

    @patch("bookwyrm.utils.db_analytics.connection")
    def test_get_cache_hit_ratio(self, mock_connection):
        """Get cache hit ratio"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (95.5, 90000, 9500)
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        ratio = self.analyzer.get_cache_hit_ratio()
        
        self.assertEqual(ratio["cache_hit_ratio"], 95.5)
        self.assertEqual(ratio["heap_read"], 90000)
        self.assertEqual(ratio["heap_hit"], 9500)

    @patch("bookwyrm.utils.db_analytics.connection")
    def test_get_cache_hit_ratio_low(self, mock_connection):
        """Handle low cache hit ratio"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (70.0, 50000, 15000)
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        ratio = self.analyzer.get_cache_hit_ratio()
        
        self.assertEqual(ratio["cache_hit_ratio"], 70.0)
        self.assertLess(ratio["cache_hit_ratio"], 90.0)


class DatabaseAnalyzerBlockingQueriesTest(TestCase):
    """Test blocking query detection"""

    def setUp(self):
        """Set up test fixtures"""
        self.analyzer = DatabaseAnalyzer()

    @patch("bookwyrm.utils.db_analytics.connection")
    def test_get_blocking_queries(self, mock_connection):
        """Get blocking queries"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (123, "bookwyrm_user", 10, "UPDATE bookwyrm_status", 456, "SELECT * FROM bookwyrm_status"),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        blocks = self.analyzer.get_blocking_queries()
        
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["blocking_pid"], 123)
        self.assertEqual(blocks[0]["blocked_pid"], 456)

    @patch("bookwyrm.utils.db_analytics.connection")
    def test_get_blocking_queries_none(self, mock_connection):
        """Handle no blocking queries"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        blocks = self.analyzer.get_blocking_queries()
        
        self.assertEqual(len(blocks), 0)


class DatabaseAnalyzerLongRunningQueriesTest(TestCase):
    """Test long-running query detection"""

    def setUp(self):
        """Set up test fixtures"""
        self.analyzer = DatabaseAnalyzer()

    @patch("bookwyrm.utils.db_analytics.connection")
    def test_get_long_running_queries(self, mock_connection):
        """Get long-running queries"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (123, "bookwyrm_user", "SELECT * FROM bookwyrm_status", 300, "active"),
            (124, "bookwyrm_user", "UPDATE bookwyrm_review", 600, "active"),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        queries = self.analyzer.get_long_running_queries()
        
        self.assertEqual(len(queries), 2)
        self.assertEqual(queries[0]["pid"], 123)
        self.assertEqual(queries[0]["duration_seconds"], 300)

    @patch("bookwyrm.utils.db_analytics.connection")
    def test_get_long_running_queries_with_min_duration(self, mock_connection):
        """Get long-running queries with minimum duration"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (124, "bookwyrm_user", "UPDATE bookwyrm_review", 600, "active"),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        queries = self.analyzer.get_long_running_queries(min_duration_seconds=500)
        
        self.assertEqual(len(queries), 1)
        self.assertGreaterEqual(queries[0]["duration_seconds"], 500)


class DatabaseAnalyzerRecommendationsTest(TestCase):
    """Test automated recommendations"""

    def setUp(self):
        """Set up test fixtures"""
        self.analyzer = DatabaseAnalyzer()

    @patch("bookwyrm.utils.db_analytics.DatabaseAnalyzer.get_cache_hit_ratio")
    @patch("bookwyrm.utils.db_analytics.DatabaseAnalyzer.detect_bloat")
    @patch("bookwyrm.utils.db_analytics.DatabaseAnalyzer.find_unused_indexes")
    @patch("bookwyrm.utils.db_analytics.DatabaseAnalyzer.get_connection_stats")
    def test_generate_recommendations_healthy(
        self, mock_connections, mock_indexes, mock_bloat, mock_cache
    ):
        """Generate recommendations for healthy database"""
        mock_cache.return_value = {"cache_hit_ratio": 98.0}
        mock_bloat.return_value = []
        mock_indexes.return_value = []
        mock_connections.return_value = {
            "active_connections": 10,
            "max_connections": 100,
            "usage_percentage": 10.0,
        }

        recommendations = self.analyzer.generate_recommendations()
        
        # No critical recommendations for healthy database
        critical = [r for r in recommendations if r["severity"] == "critical"]
        self.assertEqual(len(critical), 0)

    @patch("bookwyrm.utils.db_analytics.DatabaseAnalyzer.get_cache_hit_ratio")
    @patch("bookwyrm.utils.db_analytics.DatabaseAnalyzer.detect_bloat")
    @patch("bookwyrm.utils.db_analytics.DatabaseAnalyzer.find_unused_indexes")
    @patch("bookwyrm.utils.db_analytics.DatabaseAnalyzer.get_connection_stats")
    def test_generate_recommendations_issues(
        self, mock_connections, mock_indexes, mock_bloat, mock_cache
    ):
        """Generate recommendations for database with issues"""
        mock_cache.return_value = {"cache_hit_ratio": 75.0}
        mock_bloat.return_value = [
            {"table_name": "bookwyrm_status", "bloat_percentage": 35.0}
        ]
        mock_indexes.return_value = [
            {"index_name": "idx_unused", "size": "50 MB"}
        ]
        mock_connections.return_value = {
            "active_connections": 90,
            "max_connections": 100,
            "usage_percentage": 90.0,
        }

        recommendations = self.analyzer.generate_recommendations()
        
        # Should have multiple recommendations
        self.assertGreater(len(recommendations), 0)
        
        # Check for cache recommendation
        cache_recs = [r for r in recommendations if "cache" in r["issue"].lower()]
        self.assertGreater(len(cache_recs), 0)
        
        # Check for bloat recommendation
        bloat_recs = [r for r in recommendations if "bloat" in r["issue"].lower()]
        self.assertGreater(len(bloat_recs), 0)

    @patch("bookwyrm.utils.db_analytics.DatabaseAnalyzer.get_cache_hit_ratio")
    def test_generate_recommendations_cache_warning(self, mock_cache):
        """Generate warning for moderate cache issues"""
        mock_cache.return_value = {"cache_hit_ratio": 85.0}

        recommendations = self.analyzer.generate_recommendations()
        
        cache_recs = [r for r in recommendations if "cache" in r["issue"].lower()]
        self.assertGreater(len(cache_recs), 0)
        self.assertEqual(cache_recs[0]["severity"], "warning")
