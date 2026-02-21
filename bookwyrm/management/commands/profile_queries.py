"""Management command to profile database queries.

Provides a command-line tool for analyzing query performance and detecting issues.
"""

from django.core.management.base import BaseCommand
from django.conf import settings

from bookwyrm.utils.performance import analyze_query_performance


class Command(BaseCommand):
    """Profile database queries and analyze performance."""

    help = "Profile database queries and detect performance issues"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--min-duration",
            type=float,
            default=100.0,
            help="Minimum query duration in milliseconds to consider slow (default: 100)",
        )

    def handle(self, *args, **options):
        """Execute the query profiling command."""
        min_duration_ms = options["min_duration"]

        if not settings.DEBUG:
            self.stderr.write(
                self.style.ERROR(
                    "Query profiling is only available in DEBUG mode. "
                    "Set DEBUG=True in your settings."
                )
            )
            return

        self.stdout.write("=" * 80)
        self.stdout.write(
            self.style.MIGRATE_HEADING("Database Query Performance Analysis")
        )
        self.stdout.write("=" * 80)
        self.stdout.write("")

        # Analyze queries
        analysis = analyze_query_performance(min_duration_ms=min_duration_ms)

        if "error" in analysis:
            self.stderr.write(self.style.ERROR(analysis["error"]))
            return

        # Display results
        self.stdout.write(self.style.MIGRATE_LABEL("Query Statistics:"))
        self.stdout.write("-" * 80)
        self.stdout.write(f"Total Queries: {analysis['total_queries']}")
        self.stdout.write(
            f"Slow Queries (>{min_duration_ms}ms): "
            f"{analysis['slow_query_count']}"
        )
        self.stdout.write("")

        # Query distribution
        if analysis["query_distribution"]:
            self.stdout.write(self.style.MIGRATE_LABEL("Query Type Distribution:"))
            self.stdout.write("-" * 80)
            for query_type, count in sorted(
                analysis["query_distribution"].items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                self.stdout.write(f"  {query_type}: {count}")
            self.stdout.write("")

        # Slow queries
        if analysis["slow_queries"]:
            self.stdout.write(
                self.style.MIGRATE_LABEL(
                    f"Slowest Queries (>{min_duration_ms}ms):"
                )
            )
            self.stdout.write("-" * 80)
            for i, query in enumerate(analysis["slow_queries"][:10], 1):
                self.stdout.write(
                    f"\n{i}. {self.style.ERROR(f\"{query['duration_ms']}ms\")}"
                )
                self.stdout.write(f"   {query['sql']}...")
            self.stdout.write("")

        # Optimization opportunities
        if analysis["select_related_opportunities"]:
            self.stdout.write(
                self.style.MIGRATE_LABEL("Optimization Opportunities:")
            )
            self.stdout.write("-" * 80)
            for opp in analysis["select_related_opportunities"]:
                self.stdout.write(
                    self.style.WARNING(
                        f"Pattern executed {opp['occurrences']} times: "
                        f"{opp['pattern']}"
                    )
                )
                self.stdout.write(f"  Suggestion: {opp['suggestion']}")
                self.stdout.write("")

        self.stdout.write("=" * 80)
