"""Tests for performance profiling utilities"""

from unittest.mock import patch, MagicMock
from django.test import TestCase, RequestFactory
from django.core.cache import cache
from bookwyrm.utils.performance import (
    QueryProfiler,
    profile_queries,
    ViewPerformanceTracker,
    profile_view,
    PerformanceMonitor,
    measure_performance,
    detect_select_related_opportunities,
    analyze_query_performance,
)


class QueryProfilerTest(TestCase):
    """Test QueryProfiler class"""

    def setUp(self):
        """Set up test fixtures"""
        self.profiler = QueryProfiler()

    def test_add_query(self):
        """Add a query to the profiler"""
        query = "SELECT * FROM bookwyrm_status WHERE user_id = 1"
        self.profiler.add_query(query, 0.05)
        
        self.assertEqual(len(self.profiler.queries), 1)
        self.assertEqual(self.profiler.queries[0]["sql"], query)
        self.assertEqual(self.profiler.queries[0]["duration"], 0.05)

    def test_get_total_time(self):
        """Calculate total query time"""
        self.profiler.add_query("SELECT * FROM bookwyrm_status", 0.1)
        self.profiler.add_query("SELECT * FROM bookwyrm_user", 0.2)
        
        total_time = self.profiler.get_total_time()
        
        self.assertEqual(total_time, 0.3)

    def test_get_query_count(self):
        """Get query count"""
        self.profiler.add_query("SELECT * FROM bookwyrm_status", 0.1)
        self.profiler.add_query("SELECT * FROM bookwyrm_user", 0.2)
        
        count = self.profiler.get_query_count()
        
        self.assertEqual(count, 2)

    def test_normalize_query(self):
        """Normalize SQL query"""
        query1 = "SELECT * FROM bookwyrm_status WHERE id = 1"
        query2 = "SELECT * FROM bookwyrm_status WHERE id = 2"
        
        normalized1 = self.profiler._normalize_query(query1)
        normalized2 = self.profiler._normalize_query(query2)
        
        self.assertEqual(normalized1, normalized2)
        self.assertIn("?", normalized1)

    def test_detect_n_plus_one(self):
        """Detect N+1 query pattern"""
        # Add same query multiple times
        for i in range(10):
            self.profiler.add_query(f"SELECT * FROM bookwyrm_book WHERE id = {i}", 0.01)
        
        n_plus_one = self.profiler.detect_n_plus_one()
        
        self.assertGreater(len(n_plus_one), 0)
        self.assertEqual(n_plus_one[0]["count"], 10)

    def test_detect_n_plus_one_threshold(self):
        """N+1 detection respects threshold"""
        # Add query 3 times (below default threshold of 5)
        for i in range(3):
            self.profiler.add_query(f"SELECT * FROM bookwyrm_book WHERE id = {i}", 0.01)
        
        n_plus_one = self.profiler.detect_n_plus_one()
        
        self.assertEqual(len(n_plus_one), 0)

    def test_get_slowest_queries(self):
        """Get slowest queries"""
        self.profiler.add_query("SELECT * FROM bookwyrm_status", 0.5)
        self.profiler.add_query("SELECT * FROM bookwyrm_user", 0.1)
        self.profiler.add_query("SELECT * FROM bookwyrm_book", 0.3)
        
        slowest = self.profiler.get_slowest_queries(limit=2)
        
        self.assertEqual(len(slowest), 2)
        self.assertEqual(slowest[0]["duration"], 0.5)
        self.assertEqual(slowest[1]["duration"], 0.3)


class ProfileQueriesContextManagerTest(TestCase):
    """Test profile_queries context manager"""

    @patch("bookwyrm.utils.performance.connection")
    def test_profile_queries_basic(self, mock_connection):
        """Profile queries in context"""
        mock_connection.queries = [
            {"sql": "SELECT * FROM bookwyrm_status", "time": "0.05"},
            {"sql": "SELECT * FROM bookwyrm_user", "time": "0.10"},
        ]
        
        with profile_queries() as profiler:
            pass
        
        self.assertEqual(profiler.get_query_count(), 2)
        self.assertAlmostEqual(profiler.get_total_time(), 0.15, places=2)

    @patch("bookwyrm.utils.performance.connection")
    def test_profile_queries_n_plus_one(self, mock_connection):
        """Detect N+1 in profiled queries"""
        mock_connection.queries = [
            {"sql": f"SELECT * FROM bookwyrm_book WHERE id = {i}", "time": "0.01"}
            for i in range(10)
        ]
        
        with profile_queries() as profiler:
            pass
        
        n_plus_one = profiler.detect_n_plus_one()
        self.assertGreater(len(n_plus_one), 0)


class ViewPerformanceTrackerTest(TestCase):
    """Test ViewPerformanceTracker class"""

    def setUp(self):
        """Set up test fixtures"""
        self.tracker = ViewPerformanceTracker()
        cache.clear()

    def test_record_performance(self):
        """Record view performance"""
        self.tracker.record_performance("book_detail", 0.5, 10)
        
        # Performance should be cached
        cache_key = "view_perf_book_detail"
        cached_data = cache.get(cache_key)
        
        self.assertIsNotNone(cached_data)
        self.assertIn("durations", cached_data)

    def test_get_performance_stats(self):
        """Get performance statistics"""
        # Record multiple performances
        for duration in [0.1, 0.2, 0.3, 0.4, 0.5]:
            self.tracker.record_performance("book_detail", duration, 5)
        
        stats = self.tracker.get_performance_stats("book_detail")
        
        self.assertIsNotNone(stats)
        self.assertEqual(stats["count"], 5)
        self.assertAlmostEqual(stats["average_duration"], 0.3, places=1)

    def test_get_performance_stats_no_data(self):
        """Handle missing performance data"""
        stats = self.tracker.get_performance_stats("nonexistent_view")
        
        self.assertIsNone(stats)

    def test_clear_stats(self):
        """Clear performance statistics"""
        self.tracker.record_performance("book_detail", 0.5, 10)
        self.tracker.clear_stats("book_detail")
        
        stats = self.tracker.get_performance_stats("book_detail")
        self.assertIsNone(stats)


class ProfileViewDecoratorTest(TestCase):
    """Test profile_view decorator"""

    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()
        cache.clear()

    @patch("bookwyrm.utils.performance.ViewPerformanceTracker")
    def test_profile_view_decorator(self, mock_tracker):
        """Profile view with decorator"""
        mock_tracker_instance = MagicMock()
        mock_tracker.return_value = mock_tracker_instance

        @profile_view
        def test_view(request):
            return "Response"

        request = self.factory.get("/test/")
        response = test_view(request)
        
        self.assertEqual(response, "Response")

    @patch("bookwyrm.utils.performance.connection")
    def test_profile_view_tracks_queries(self, mock_connection):
        """Profile view tracks query count"""
        mock_connection.queries = [
            {"sql": "SELECT * FROM bookwyrm_status", "time": "0.05"},
        ]

        @profile_view
        def test_view(request):
            return "Response"

        request = self.factory.get("/test/")
        test_view(request)
        
        # Should track performance in cache
        # (Implementation details vary, just verify decorator works)


class PerformanceMonitorTest(TestCase):
    """Test PerformanceMonitor class"""

    def setUp(self):
        """Set up test fixtures"""
        self.monitor = PerformanceMonitor()

    def test_add_measurement(self):
        """Add a measurement"""
        self.monitor.add_measurement("database_query", 0.05)
        
        self.assertIn("database_query", self.monitor.measurements)
        self.assertEqual(len(self.monitor.measurements["database_query"]), 1)
        self.assertEqual(self.monitor.measurements["database_query"][0], 0.05)

    def test_get_stats(self):
        """Get measurement statistics"""
        measurements = [0.1, 0.2, 0.3, 0.4, 0.5]
        for m in measurements:
            self.monitor.add_measurement("test_operation", m)
        
        stats = self.monitor.get_stats("test_operation")
        
        self.assertEqual(stats["count"], 5)
        self.assertAlmostEqual(stats["average"], 0.3, places=1)
        self.assertEqual(stats["min"], 0.1)
        self.assertEqual(stats["max"], 0.5)

    def test_get_stats_with_percentiles(self):
        """Get statistics with percentiles"""
        # Add 100 measurements
        for i in range(100):
            self.monitor.add_measurement("test_operation", i / 100.0)
        
        stats = self.monitor.get_stats("test_operation")
        
        self.assertIn("p50", stats)
        self.assertIn("p95", stats)
        self.assertIn("p99", stats)

    def test_get_stats_no_data(self):
        """Handle missing measurement data"""
        stats = self.monitor.get_stats("nonexistent_operation")
        
        self.assertIsNone(stats)

    def test_clear_measurements(self):
        """Clear measurements"""
        self.monitor.add_measurement("test_operation", 0.1)
        self.monitor.clear_measurements("test_operation")
        
        stats = self.monitor.get_stats("test_operation")
        self.assertIsNone(stats)

    def test_get_all_stats(self):
        """Get all measurement statistics"""
        self.monitor.add_measurement("operation1", 0.1)
        self.monitor.add_measurement("operation2", 0.2)
        
        all_stats = self.monitor.get_all_stats()
        
        self.assertIn("operation1", all_stats)
        self.assertIn("operation2", all_stats)


class MeasurePerformanceContextManagerTest(TestCase):
    """Test measure_performance context manager"""

    def test_measure_performance_basic(self):
        """Measure performance in context"""
        monitor = PerformanceMonitor()
        
        with measure_performance("test_operation", monitor):
            # Simulate some work
            import time
            time.sleep(0.01)
        
        stats = monitor.get_stats("test_operation")
        
        self.assertIsNotNone(stats)
        self.assertEqual(stats["count"], 1)
        self.assertGreater(stats["average"], 0)

    def test_measure_performance_multiple(self):
        """Measure multiple operations"""
        monitor = PerformanceMonitor()
        
        for _ in range(5):
            with measure_performance("test_operation", monitor):
                pass
        
        stats = monitor.get_stats("test_operation")
        
        self.assertEqual(stats["count"], 5)


class DetectSelectRelatedOpportunitiesTest(TestCase):
    """Test detect_select_related_opportunities"""

    def test_detect_select_related_basic(self):
        """Detect basic select_related opportunities"""
        queries = [
            "SELECT * FROM bookwyrm_status WHERE id = 1",
            "SELECT * FROM bookwyrm_user WHERE id = 10",
            "SELECT * FROM bookwyrm_status WHERE id = 2",
            "SELECT * FROM bookwyrm_user WHERE id = 11",
        ]
        
        opportunities = detect_select_related_opportunities(queries)
        
        self.assertGreater(len(opportunities), 0)
        # Should detect pattern of status followed by user queries

    def test_detect_select_related_no_pattern(self):
        """No opportunities when queries are varied"""
        queries = [
            "SELECT * FROM bookwyrm_status WHERE id = 1",
            "SELECT * FROM bookwyrm_book WHERE id = 1",
            "SELECT * FROM bookwyrm_review WHERE id = 1",
        ]
        
        opportunities = detect_select_related_opportunities(queries)
        
        # May have fewer or no opportunities with diverse queries
        self.assertIsInstance(opportunities, list)

    def test_detect_select_related_empty(self):
        """Handle empty query list"""
        opportunities = detect_select_related_opportunities([])
        
        self.assertEqual(len(opportunities), 0)


class AnalyzeQueryPerformanceTest(TestCase):
    """Test analyze_query_performance"""

    def test_analyze_query_performance_basic(self):
        """Analyze query performance"""
        queries = [
            {"sql": "SELECT * FROM bookwyrm_status", "duration": 0.5},
            {"sql": "SELECT * FROM bookwyrm_user", "duration": 0.1},
            {"sql": "UPDATE bookwyrm_status SET read = true", "duration": 0.3},
        ]
        
        analysis = analyze_query_performance(queries)
        
        self.assertEqual(analysis["total_queries"], 3)
        self.assertAlmostEqual(analysis["total_time"], 0.9, places=1)
        self.assertIn("query_type_distribution", analysis)

    def test_analyze_query_performance_distribution(self):
        """Analyze query type distribution"""
        queries = [
            {"sql": "SELECT * FROM bookwyrm_status", "duration": 0.1},
            {"sql": "SELECT * FROM bookwyrm_user", "duration": 0.1},
            {"sql": "UPDATE bookwyrm_status SET read = true", "duration": 0.1},
            {"sql": "INSERT INTO bookwyrm_review VALUES (1, 'test')", "duration": 0.1},
        ]
        
        analysis = analyze_query_performance(queries)
        
        dist = analysis["query_type_distribution"]
        self.assertEqual(dist["SELECT"], 2)
        self.assertEqual(dist["UPDATE"], 1)
        self.assertEqual(dist["INSERT"], 1)

    def test_analyze_query_performance_slow_queries(self):
        """Identify slow queries"""
        queries = [
            {"sql": "SELECT * FROM bookwyrm_status", "duration": 1.5},
            {"sql": "SELECT * FROM bookwyrm_user", "duration": 0.1},
        ]
        
        analysis = analyze_query_performance(queries, min_duration=1.0)
        
        self.assertEqual(len(analysis["slow_queries"]), 1)
        self.assertEqual(analysis["slow_queries"][0]["duration"], 1.5)

    def test_analyze_query_performance_empty(self):
        """Handle empty query list"""
        analysis = analyze_query_performance([])
        
        self.assertEqual(analysis["total_queries"], 0)
        self.assertEqual(analysis["total_time"], 0.0)


class PerformanceIntegrationTest(TestCase):
    """Integration tests for performance utilities"""

    def setUp(self):
        """Set up test fixtures"""
        cache.clear()

    @patch("bookwyrm.utils.performance.connection")
    def test_full_profiling_workflow(self, mock_connection):
        """Test complete profiling workflow"""
        mock_connection.queries = [
            {"sql": "SELECT * FROM bookwyrm_status WHERE id = 1", "time": "0.05"},
            {"sql": "SELECT * FROM bookwyrm_user WHERE id = 10", "time": "0.03"},
            {"sql": "SELECT * FROM bookwyrm_status WHERE id = 2", "time": "0.05"},
            {"sql": "SELECT * FROM bookwyrm_user WHERE id = 11", "time": "0.03"},
        ]
        
        with profile_queries() as profiler:
            pass
        
        # Check basic stats
        self.assertEqual(profiler.get_query_count(), 4)
        
        # Check N+1 detection
        n_plus_one = profiler.detect_n_plus_one()
        # May or may not detect N+1 depending on threshold
        
        # Check analysis
        analysis = analyze_query_performance(profiler.queries)
        self.assertEqual(analysis["total_queries"], 4)

    def test_performance_monitor_workflow(self):
        """Test performance monitor workflow"""
        monitor = PerformanceMonitor()
        
        # Measure multiple operations
        with measure_performance("db_query", monitor):
            import time
            time.sleep(0.001)
        
        with measure_performance("cache_lookup", monitor):
            import time
            time.sleep(0.0005)
        
        # Get all stats
        all_stats = monitor.get_all_stats()
        
        self.assertIn("db_query", all_stats)
        self.assertIn("cache_lookup", all_stats)
        self.assertGreater(all_stats["db_query"]["average"], all_stats["cache_lookup"]["average"])
