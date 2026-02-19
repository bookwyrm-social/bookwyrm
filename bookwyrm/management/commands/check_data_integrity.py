"""Management command to check data integrity.

Performs comprehensive data integrity checks and reports issues.
"""

import json
from django.core.management.base import BaseCommand

from bookwyrm.utils.data_integrity import (
    DataIntegrityChecker,
    find_duplicate_records,
    validate_foreign_keys,
)
from bookwyrm import models


class Command(BaseCommand):
    """Check data integrity across the database."""

    help = "Check data integrity and report issues"

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
            nargs="+",
            choices=[
                "orphaned",
                "relationships",
                "federation",
                "duplicates",
                "foreign-keys",
                "all",
            ],
            default=["all"],
            help="Types of checks to perform",
        )
        parser.add_argument(
            "--check-duplicates-in",
            type=str,
            help="Model name to check for duplicates (e.g., 'User', 'Book')",
        )

    def handle(self, *args, **options):
        """Execute the data integrity check command."""
        format_type = options["format"]
        checks = options["check"]
        
        if "all" in checks:
            checks = ["orphaned", "relationships", "federation", "duplicates", "foreign-keys"]

        checker = DataIntegrityChecker()
        results = {}

        # Run integrity checks
        if any(check in checks for check in ["orphaned", "relationships", "federation"]):
            check_results = checker.check_all()
            results["integrity_checks"] = check_results

        # Check for duplicates
        if "duplicates" in checks:
            duplicate_results = []
            
            # Check common models for duplicates
            models_to_check = [
                ("User", ["email"], models.User),
                ("Author", ["name"], models.Author),
                ("FederatedServer", ["server_name"], models.FederatedServer),
            ]
            
            for model_name, fields, model_class in models_to_check:
                dups = find_duplicate_records(model_class, fields)
                if dups:
                    duplicate_results.extend(dups)
            
            results["duplicates"] = duplicate_results

        # Validate foreign keys
        if "foreign-keys" in checks:
            fk_issues = validate_foreign_keys()
            results["foreign_key_issues"] = fk_issues

        # Output results
        if format_type == "json":
            self._output_json(results)
        else:
            self._output_text(results, checker)

    def _output_json(self, results):
        """Output results in JSON format."""
        self.stdout.write(json.dumps(results, indent=2, default=str))

    def _output_text(self, results, checker):
        """Output results in human-readable text format."""
        self.stdout.write("=" * 80)
        self.stdout.write(
            self.style.MIGRATE_HEADING("BookWyrm Data Integrity Check")
        )
        self.stdout.write("=" * 80)
        self.stdout.write("")

        # Integrity check results
        if "integrity_checks" in results:
            self._display_integrity_checks(results["integrity_checks"])

        # Duplicate results
        if "duplicates" in results:
            self._display_duplicates(results["duplicates"])

        # Foreign key issues
        if "foreign_key_issues" in results:
            self._display_foreign_key_issues(results["foreign_key_issues"])

        # Summary
        self._display_summary(results)

    def _display_integrity_checks(self, check_results):
        """Display integrity check results."""
        issues = check_results.get("issues", [])
        warnings = check_results.get("warnings", [])

        # Display issues
        if issues:
            self.stdout.write(
                self.style.ERROR(f"\n⚠ Found {len(issues)} Issue(s):")
            )
            self.stdout.write("-" * 80)
            
            for i, issue in enumerate(issues, 1):
                self.stdout.write(f"\n{i}. {issue['type'].upper()} - {issue['model']}")
                self.stdout.write(f"   Count: {issue['count']}")
                self.stdout.write(f"   Description: {issue['description']}")
                if "action" in issue:
                    self.stdout.write(f"   Action: {issue['action']}")
        else:
            self.stdout.write(
                self.style.SUCCESS("\n✓ No critical issues found")
            )

        # Display warnings
        if warnings:
            self.stdout.write(
                self.style.WARNING(f"\n⚠ Found {len(warnings)} Warning(s):")
            )
            self.stdout.write("-" * 80)
            
            for i, warning in enumerate(warnings, 1):
                self.stdout.write(f"\n{i}. {warning['type'].upper()} - {warning['model']}")
                self.stdout.write(f"   Count: {warning['count']}")
                self.stdout.write(f"   Description: {warning['description']}")
                if "action" in warning:
                    self.stdout.write(f"   Action: {warning['action']}")
        else:
            self.stdout.write(
                self.style.SUCCESS("\n✓ No warnings")
            )

        self.stdout.write("")

    def _display_duplicates(self, duplicates):
        """Display duplicate record information."""
        self.stdout.write(self.style.MIGRATE_LABEL("\nDuplicate Records:"))
        self.stdout.write("-" * 80)

        if not duplicates:
            self.stdout.write(self.style.SUCCESS("No duplicates found"))
        else:
            for dup in duplicates:
                self.stdout.write(f"\nModel: {dup['model']}")
                self.stdout.write(f"Count: {self.style.ERROR(str(dup['count']))}")
                self.stdout.write("Fields:")
                for field, value in dup["fields"].items():
                    self.stdout.write(f"  {field}: {value}")

        self.stdout.write("")

    def _display_foreign_key_issues(self, issues):
        """Display foreign key validation issues."""
        self.stdout.write(self.style.MIGRATE_LABEL("\nForeign Key Issues:"))
        self.stdout.write("-" * 80)

        if not issues:
            self.stdout.write(self.style.SUCCESS("No foreign key issues found"))
        else:
            for issue in issues:
                self.stdout.write(f"\n{issue['type'].upper()}")
                self.stdout.write(f"Model: {issue['model']}")
                self.stdout.write(f"Field: {issue['field']}")
                self.stdout.write(f"Count: {self.style.ERROR(str(issue['count']))}")
                self.stdout.write(f"Description: {issue['description']}")

        self.stdout.write("")

    def _display_summary(self, results):
        """Display summary of all checks."""
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.MIGRATE_HEADING("Summary"))
        self.stdout.write("-" * 80)

        total_issues = 0
        total_warnings = 0

        if "integrity_checks" in results:
            total_issues += results["integrity_checks"].get("issue_count", 0)
            total_warnings += results["integrity_checks"].get("warning_count", 0)

        if "duplicates" in results:
            total_issues += len(results["duplicates"])

        if "foreign_key_issues" in results:
            total_issues += len(results["foreign_key_issues"])

        if total_issues > 0:
            self.stdout.write(
                f"Total Issues: {self.style.ERROR(str(total_issues))}"
            )
        else:
            self.stdout.write(
                f"Total Issues: {self.style.SUCCESS('0')}"
            )

        if total_warnings > 0:
            self.stdout.write(
                f"Total Warnings: {self.style.WARNING(str(total_warnings))}"
            )
        else:
            self.stdout.write(
                f"Total Warnings: {self.style.SUCCESS('0')}"
            )

        self.stdout.write("=" * 80)
