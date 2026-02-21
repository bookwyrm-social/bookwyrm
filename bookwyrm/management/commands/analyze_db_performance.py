"""Management command to analyze database performance and generate reports.

Provides detailed analysis of database performance, including connection stats,
table statistics, index usage, query performance, and optimization recommendations.
"""

import json
from django.core.management.base import BaseCommand

from bookwyrm.utils.db_analytics import DatabaseAnalyzer


class Command(BaseCommand):
    """Analyze database performance and provide optimization recommendations."""

    help = "Analyze database performance and generate detailed reports"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--format",
            type=str,
            default="text",
            choices=["text", "json"],
            help="Output format (text or json)",
        )
        parser.add_argument(
            "--analysis",
            type=str,
            nargs="+",
            choices=[
                "connections",
                "size",
                "tables",
                "indexes",
                "queries",
                "bloat",
                "cache",
                "blocking",
                "long-running",
                "unused-indexes",
                "recommendations",
                "all",
            ],
            default=["all"],
            help="Types of analysis to perform",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=20,
            help="Limit number of results for table/index statistics",
        )
        parser.add_argument(
            "--min-duration",
            type=int,
            default=60,
            help="Minimum duration in seconds for long-running queries",
        )
        parser.add_argument(
            "--min-index-size",
            type=int,
            default=1,
            help="Minimum size in MB for unused index detection",
        )

    def handle(self, *args, **options):
        """Execute the database analysis command."""
        format_type = options["format"]
        analyses = options["analysis"]
        limit = options["limit"]
        min_duration = options["min_duration"]
        min_index_size = options["min_index_size"]

        if "all" in analyses:
            analyses = [
                "connections",
                "size",
                "tables",
                "indexes",
                "queries",
                "bloat",
                "cache",
                "blocking",
                "long-running",
                "unused-indexes",
                "recommendations",
            ]

        analyzer = DatabaseAnalyzer()
        results = {}

        # Perform requested analyses
        if "connections" in analyses:
            results["connection_stats"] = analyzer.get_connection_stats()

        if "size" in analyses:
            results["size_stats"] = analyzer.get_database_size_stats()

        if "tables" in analyses:
            results["table_stats"] = analyzer.get_table_statistics(limit=limit)

        if "indexes" in analyses:
            results["index_stats"] = analyzer.get_index_statistics(limit=limit)

        if "queries" in analyses:
            results["query_performance"] = analyzer.get_query_performance_stats()

        if "bloat" in analyses:
            results["bloat_detection"] = analyzer.detect_bloat()

        if "cache" in analyses:
            results["cache_hit_ratio"] = analyzer.get_cache_hit_ratio()

        if "blocking" in analyses:
            results["blocking_queries"] = analyzer.get_blocking_queries()

        if "long-running" in analyses:
            results["long_running_queries"] = analyzer.get_long_running_queries(
                min_duration_seconds=min_duration
            )

        if "unused-indexes" in analyses:
            results["unused_indexes"] = analyzer.find_unused_indexes(
                min_size_mb=min_index_size
            )

        if "recommendations" in analyses:
            results["recommendations"] = analyzer.generate_recommendations()

        # Output results
        if format_type == "json":
            self._output_json(results)
        else:
            self._output_text(results, analyses)

    def _output_json(self, results):
        """Output results in JSON format."""
        # Convert datetime objects to strings for JSON serialization
        import datetime

        def serialize(obj):
            if isinstance(obj, datetime.datetime):
                return obj.isoformat()
            if isinstance(obj, datetime.date):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        self.stdout.write(json.dumps(results, indent=2, default=serialize))

    def _output_text(self, results, analyses):
        """Output results in human-readable text format."""
        self.stdout.write("=" * 80)
        self.stdout.write(
            self.style.MIGRATE_HEADING("BookWyrm Database Performance Analysis")
        )
        self.stdout.write("=" * 80)
        self.stdout.write("")

        # Connection Statistics
        if "connection_stats" in results:
            self._display_connection_stats(results["connection_stats"])

        # Size Statistics
        if "size_stats" in results:
            self._display_size_stats(results["size_stats"])

        # Cache Hit Ratio
        if "cache_hit_ratio" in results:
            self._display_cache_stats(results["cache_hit_ratio"])

        # Table Statistics
        if "table_stats" in results:
            self._display_table_stats(results["table_stats"])

        # Index Statistics
        if "index_stats" in results:
            self._display_index_stats(results["index_stats"])

        # Query Performance
        if "query_performance" in results:
            self._display_query_performance(results["query_performance"])

        # Bloat Detection
        if "bloat_detection" in results:
            self._display_bloat_detection(results["bloat_detection"])

        # Blocking Queries
        if "blocking_queries" in results:
            self._display_blocking_queries(results["blocking_queries"])

        # Long Running Queries
        if "long_running_queries" in results:
            self._display_long_running_queries(results["long_running_queries"])

        # Unused Indexes
        if "unused_indexes" in results:
            self._display_unused_indexes(results["unused_indexes"])

        # Recommendations
        if "recommendations" in results:
            self._display_recommendations(results["recommendations"])

    def _display_connection_stats(self, stats):
        """Display connection statistics."""
        self.stdout.write(self.style.MIGRATE_LABEL("\nConnection Statistics:"))
        self.stdout.write("-" * 80)
        self.stdout.write(f"Total Connections: {stats['total_connections']}")
        self.stdout.write(f"Active Connections: {stats['active_connections']}")
        self.stdout.write(f"Idle Connections: {stats['idle_connections']}")
        self.stdout.write(
            f"Idle in Transaction: {stats['idle_in_transaction']}"
        )
        self.stdout.write(f"Max Connections: {stats['max_connections']}")

        usage_pct = stats["connection_usage_percent"]
        if usage_pct > 80:
            style = self.style.ERROR
        elif usage_pct > 60:
            style = self.style.WARNING
        else:
            style = self.style.SUCCESS

        self.stdout.write(f"Connection Usage: {style(f'{usage_pct}%')}")
        self.stdout.write("")

    def _display_size_stats(self, stats):
        """Display database size statistics."""
        self.stdout.write(self.style.MIGRATE_LABEL("\nDatabase Size:"))
        self.stdout.write("-" * 80)
        self.stdout.write(f"Total Size: {stats['database_size']}")
        self.stdout.write("")
        self.stdout.write("Largest Tables:")
        for i, table in enumerate(stats["largest_tables"][:10], 1):
            self.stdout.write(
                f"  {i}. {table['schema']}.{table['table']}: {table['size']}"
            )
        self.stdout.write("")

    def _display_cache_stats(self, stats):
        """Display cache hit ratio statistics."""
        self.stdout.write(self.style.MIGRATE_LABEL("\nCache Hit Ratio:"))
        self.stdout.write("-" * 80)

        table_ratio = stats["table_cache_hit_ratio"]
        index_ratio = stats["index_cache_hit_ratio"]

        # Color code based on performance
        def ratio_style(ratio):
            if ratio >= 95:
                return self.style.SUCCESS
            elif ratio >= 90:
                return self.style.WARNING
            else:
                return self.style.ERROR

        self.stdout.write(
            f"Table Cache Hit Ratio: {ratio_style(table_ratio)(f'{table_ratio}%')}"
        )
        self.stdout.write(
            f"Index Cache Hit Ratio: {ratio_style(index_ratio)(f'{index_ratio}%')}"
        )
        self.stdout.write(f"Heap Blocks Read: {stats['heap_blocks_read']}")
        self.stdout.write(f"Heap Blocks Hit: {stats['heap_blocks_hit']}")
        self.stdout.write(f"Index Blocks Read: {stats['index_blocks_read']}")
        self.stdout.write(f"Index Blocks Hit: {stats['index_blocks_hit']}")
        self.stdout.write("")

    def _display_table_stats(self, tables):
        """Display table statistics."""
        self.stdout.write(self.style.MIGRATE_LABEL("\nTable Statistics:"))
        self.stdout.write("-" * 80)

        if not tables:
            self.stdout.write("No tables found.")
            self.stdout.write("")
            return

        for table in tables[:10]:
            self.stdout.write(f"\n{table['schemaname']}.{table['tablename']}:")
            self.stdout.write(f"  Total Size: {table['total_size']}")
            self.stdout.write(f"  Table Size: {table['table_size']}")
            self.stdout.write(f"  Index Size: {table['index_size']}")
            self.stdout.write(f"  Row Count: {table['row_count']:,}")
            self.stdout.write(f"  Dead Rows: {table['dead_rows']:,}")

            dead_pct = table["dead_row_percent"]
            if dead_pct > 20:
                style = self.style.ERROR
            elif dead_pct > 10:
                style = self.style.WARNING
            else:
                style = self.style.SUCCESS

            self.stdout.write(f"  Dead Row %: {style(f'{dead_pct}%')}")
            self.stdout.write(f"  Sequential Scans: {table['seq_scan']:,}")
            self.stdout.write(f"  Index Scans: {table['idx_scan']:,}")

            idx_pct = table["index_usage_percent"]
            if idx_pct < 50 and (table["seq_scan"] + table["idx_scan"]) > 100:
                style = self.style.ERROR
            elif idx_pct < 80:
                style = self.style.WARNING
            else:
                style = self.style.SUCCESS

            self.stdout.write(f"  Index Usage %: {style(f'{idx_pct}%')}")

        self.stdout.write("")

    def _display_index_stats(self, indexes):
        """Display index statistics."""
        self.stdout.write(self.style.MIGRATE_LABEL("\nIndex Statistics:"))
        self.stdout.write("-" * 80)

        if not indexes:
            self.stdout.write("No indexes found.")
            self.stdout.write("")
            return

        for idx in indexes[:10]:
            self.stdout.write(
                f"\n{idx['schemaname']}.{idx['tablename']}.{idx['indexname']}:"
            )
            self.stdout.write(f"  Size: {idx['index_size']}")
            self.stdout.write(f"  Scans: {idx['index_scans']:,}")
            self.stdout.write(f"  Tuples Read: {idx['tuples_read']:,}")
            self.stdout.write(f"  Tuples Fetched: {idx['tuples_fetched']:,}")

            status = idx["usage_status"]
            if status == "UNUSED":
                style = self.style.ERROR
            elif status == "RARELY USED":
                style = self.style.WARNING
            else:
                style = self.style.SUCCESS

            self.stdout.write(f"  Status: {style(status)}")

        self.stdout.write("")

    def _display_query_performance(self, perf):
        """Display query performance statistics."""
        self.stdout.write(self.style.MIGRATE_LABEL("\nQuery Performance:"))
        self.stdout.write("-" * 80)

        if not perf.get("available"):
            self.stdout.write(
                self.style.WARNING(
                    "pg_stat_statements extension not available. "
                    "Enable it for query performance tracking."
                )
            )
            self.stdout.write("")
            return

        # Slowest queries
        self.stdout.write("\nSlowest Queries (by mean execution time):")
        for i, query in enumerate(perf.get("slow_queries", [])[:5], 1):
            self.stdout.write(f"\n{i}. {query['query_preview']}...")
            self.stdout.write(f"   Calls: {query['calls']:,}")
            self.stdout.write(
                f"   Mean Time: {self.style.ERROR(f\"{query['mean_time_ms']:.2f}ms\")}"
            )
            self.stdout.write(f"   Max Time: {query['max_time_ms']:.2f}ms")
            self.stdout.write(f"   Total Time: {query['total_time_ms']:.2f}ms")

        # Most called queries
        self.stdout.write("\n\nMost Frequently Called Queries:")
        for i, query in enumerate(perf.get("most_called_queries", [])[:5], 1):
            self.stdout.write(f"\n{i}. {query['query_preview']}...")
            self.stdout.write(f"   Calls: {query['calls']:,}")
            self.stdout.write(f"   Mean Time: {query['mean_time_ms']:.2f}ms")
            self.stdout.write(f"   Total Time: {query['total_time_ms']:.2f}ms")

        self.stdout.write("")

    def _display_bloat_detection(self, bloat):
        """Display bloat detection results."""
        self.stdout.write(self.style.MIGRATE_LABEL("\nTable Bloat Detection:"))
        self.stdout.write("-" * 80)

        if not bloat:
            self.stdout.write(self.style.SUCCESS("No significant bloat detected."))
            self.stdout.write("")
            return

        self.stdout.write(
            self.style.WARNING(f"Found {len(bloat)} table(s) with significant bloat:")
        )
        for table in bloat:
            self.stdout.write(f"\n{table['schemaname']}.{table['tablename']}:")
            self.stdout.write(f"  Size: {table['total_size']}")
            self.stdout.write(f"  Live Tuples: {table['live_tuples']:,}")
            self.stdout.write(
                f"  Dead Tuples: {self.style.ERROR(f\"{table['dead_tuples']:,}\")}"
            )
            self.stdout.write(
                f"  Bloat: {self.style.ERROR(f\"{table['bloat_percent']}%\")}"
            )
            self.stdout.write(f"  Last Vacuum: {table['last_vacuum']}")
            self.stdout.write(f"  Last Autovacuum: {table['last_autovacuum']}")

        self.stdout.write("")

    def _display_blocking_queries(self, blocking):
        """Display blocking query information."""
        self.stdout.write(self.style.MIGRATE_LABEL("\nBlocking Queries:"))
        self.stdout.write("-" * 80)

        if not blocking:
            self.stdout.write(self.style.SUCCESS("No blocking queries detected."))
            self.stdout.write("")
            return

        self.stdout.write(
            self.style.ERROR(f"Found {len(blocking)} blocking situation(s):")
        )
        for i, block in enumerate(blocking, 1):
            self.stdout.write(f"\n{i}. Blocked PID {block['blocked_pid']}:")
            self.stdout.write(f"   Blocked User: {block['blocked_user']}")
            self.stdout.write(f"   Blocked Query: {block['blocked_query'][:100]}...")
            self.stdout.write(f"   Blocking PID: {block['blocking_pid']}")
            self.stdout.write(f"   Blocking User: {block['blocking_user']}")
            self.stdout.write(f"   Blocking Query: {block['blocking_query'][:100]}...")

        self.stdout.write("")

    def _display_long_running_queries(self, queries):
        """Display long-running query information."""
        self.stdout.write(self.style.MIGRATE_LABEL("\nLong Running Queries:"))
        self.stdout.write("-" * 80)

        if not queries:
            self.stdout.write(self.style.SUCCESS("No long-running queries detected."))
            self.stdout.write("")
            return

        self.stdout.write(
            self.style.WARNING(f"Found {len(queries)} long-running query(ies):")
        )
        for i, query in enumerate(queries, 1):
            self.stdout.write(f"\n{i}. PID {query['pid']}:")
            self.stdout.write(f"   User: {query['usename']}")
            self.stdout.write(f"   State: {query['state']}")
            self.stdout.write(
                f"   Duration: {self.style.ERROR(f\"{query['duration_seconds']}s\")}"
            )
            self.stdout.write(f"   Started: {query['query_start']}")
            self.stdout.write(f"   Query: {query['query'][:200]}...")

        self.stdout.write("")

    def _display_unused_indexes(self, indexes):
        """Display unused index information."""
        self.stdout.write(self.style.MIGRATE_LABEL("\nUnused/Rarely Used Indexes:"))
        self.stdout.write("-" * 80)

        if not indexes:
            self.stdout.write(self.style.SUCCESS("No unused indexes detected."))
            self.stdout.write("")
            return

        self.stdout.write(
            self.style.WARNING(
                f"Found {len(indexes)} unused or rarely-used index(es):"
            )
        )
        for idx in indexes:
            self.stdout.write(
                f"\n{idx['schemaname']}.{idx['tablename']}.{idx['indexname']}:"
            )
            self.stdout.write(f"  Size: {idx['index_size']}")
            self.stdout.write(
                f"  Scans: {self.style.ERROR(str(idx['index_scans']))}"
            )
            self.stdout.write(
                f"  Consider: DROP INDEX {idx['schemaname']}.{idx['indexname']};"
            )

        self.stdout.write("")

    def _display_recommendations(self, recommendations):
        """Display optimization recommendations."""
        self.stdout.write(self.style.MIGRATE_LABEL("\nOptimization Recommendations:"))
        self.stdout.write("-" * 80)

        for rec in recommendations:
            if rec.startswith("✓"):
                self.stdout.write(self.style.SUCCESS(rec))
            else:
                self.stdout.write(self.style.WARNING(rec))

        self.stdout.write("")
