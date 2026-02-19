"""Management command to check system health and report status.

This command performs comprehensive health checks on all critical BookWyrm
components and provides detailed reporting.
"""

import json
import sys
from django.core.management.base import BaseCommand
from django.utils import timezone

from bookwyrm.utils.health_checks import HealthChecker


class Command(BaseCommand):
    """Check system health and report status."""

    help = "Perform health checks on BookWyrm system components"

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
            "--check",
            type=str,
            help="Run only a specific check (database, redis_broker, redis_activity, celery, cache, storage, email_config, federation)",
        )
        parser.add_argument(
            "--fail-on-unhealthy",
            action="store_true",
            help="Exit with error code if any component is unhealthy",
        )
        parser.add_argument(
            "--fail-on-degraded",
            action="store_true",
            help="Exit with error code if any component is degraded or unhealthy",
        )

    def handle(self, *args, **options):
        """Execute the health check command."""
        format_type = options["format"]
        specific_check = options.get("check")
        fail_on_unhealthy = options.get("fail_on_unhealthy", False)
        fail_on_degraded = options.get("fail_on_degraded", False)

        checker = HealthChecker()

        # Run specific check or all checks
        if specific_check:
            check_method = getattr(checker, f"check_{specific_check}", None)
            if check_method:
                result = check_method()
                results = [result]
            else:
                self.stderr.write(
                    self.style.ERROR(
                        f"Unknown check: {specific_check}. "
                        "Available checks: database, redis_broker, redis_activity, "
                        "celery, cache, storage, email_config, federation"
                    )
                )
                sys.exit(1)
        else:
            results = checker.check_all()

        summary = checker.get_summary()

        # Output results
        if format_type == "json":
            self._output_json(summary)
        else:
            self._output_text(results, summary)

        # Determine exit code
        exit_code = 0
        if fail_on_degraded and summary["status"] in ["degraded", "unhealthy"]:
            exit_code = 1
        elif fail_on_unhealthy and summary["status"] == "unhealthy":
            exit_code = 1

        if exit_code != 0:
            sys.exit(exit_code)

    def _output_text(self, results, summary):
        """Output results in human-readable text format."""
        self.stdout.write("=" * 70)
        self.stdout.write(
            self.style.MIGRATE_HEADING("BookWyrm System Health Check")
        )
        self.stdout.write(f"Time: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.stdout.write("=" * 70)
        self.stdout.write("")

        # Display individual check results
        for result in results:
            self._display_result(result)
            self.stdout.write("")

        # Display summary
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.MIGRATE_HEADING("Summary"))
        self.stdout.write("-" * 70)

        status = summary["status"]
        if status == "healthy":
            status_style = self.style.SUCCESS
        elif status == "degraded":
            status_style = self.style.WARNING
        else:
            status_style = self.style.ERROR

        self.stdout.write(f"Overall Status: {status_style(status.upper())}")
        self.stdout.write(f"Message: {summary['message']}")
        self.stdout.write(f"Healthy: {summary['healthy']}/{summary['total']}")
        self.stdout.write(f"Degraded: {summary['degraded']}/{summary['total']}")
        self.stdout.write(f"Unhealthy: {summary['unhealthy']}/{summary['total']}")
        self.stdout.write("=" * 70)

    def _display_result(self, result):
        """Display a single health check result."""
        # Status indicator
        if result.status == "healthy":
            status_icon = "✓"
            status_style = self.style.SUCCESS
        elif result.status == "degraded":
            status_icon = "⚠"
            status_style = self.style.WARNING
        else:
            status_icon = "✗"
            status_style = self.style.ERROR

        # Header
        self.stdout.write(
            f"{status_icon} {self.style.MIGRATE_LABEL(result.name.upper())}: "
            f"{status_style(result.status)}"
        )

        # Message
        self.stdout.write(f"  Message: {result.message}")

        # Duration
        self.stdout.write(f"  Duration: {result.duration_ms:.2f}ms")

        # Details
        if result.details:
            self.stdout.write("  Details:")
            for key, value in result.details.items():
                if key == "error":
                    self.stdout.write(f"    {key}: {self.style.ERROR(str(value))}")
                elif isinstance(value, dict):
                    self.stdout.write(f"    {key}:")
                    for sub_key, sub_value in value.items():
                        self.stdout.write(f"      {sub_key}: {sub_value}")
                else:
                    self.stdout.write(f"    {key}: {value}")

    def _output_json(self, summary):
        """Output results in JSON format."""
        self.stdout.write(json.dumps(summary, indent=2))
