"""Management command to create database backups.

Provides a simple interface for backing up the PostgreSQL database.
"""

import sys
from django.core.management.base import BaseCommand

from bookwyrm.utils.backup import BackupManager


class Command(BaseCommand):
    """Create a database backup."""

    help = "Create a PostgreSQL database backup using pg_dump"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--backup-dir",
            type=str,
            help="Directory to store backup (default: BASE_DIR/backups)",
        )
        parser.add_argument(
            "--no-compress",
            action="store_true",
            help="Don't compress the backup",
        )
        parser.add_argument(
            "--format",
            type=str,
            default="custom",
            choices=["custom", "plain", "directory", "tar"],
            help="Backup format (default: custom)",
        )
        parser.add_argument(
            "--verify",
            action="store_true",
            help="Verify backup after creation",
        )

    def handle(self, *args, **options):
        """Execute the database backup command."""
        backup_dir = options.get("backup_dir")
        compress = not options.get("no_compress", False)
        backup_format = options["format"]
        verify = options.get("verify", False)

        manager = BackupManager(backup_dir=backup_dir)

        self.stdout.write("=" * 70)
        self.stdout.write(
            self.style.MIGRATE_HEADING("BookWyrm Database Backup")
        )
        self.stdout.write("=" * 70)
        self.stdout.write("")

        # Create backup
        self.stdout.write("Creating database backup...")
        success, message, backup_path = manager.create_database_backup(
            compress=compress, format=backup_format
        )

        if success:
            self.stdout.write(self.style.SUCCESS(f"✓ {message}"))

            # Verify if requested
            if verify and backup_path:
                self.stdout.write("\nVerifying backup...")
                verify_success, verify_message = manager.verify_database_backup(
                    backup_path
                )

                if verify_success:
                    self.stdout.write(
                        self.style.SUCCESS(f"✓ {verify_message}")
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f"✗ {verify_message}")
                    )
                    sys.exit(1)

        else:
            self.stdout.write(self.style.ERROR(f"✗ {message}"))
            sys.exit(1)

        self.stdout.write("\n" + "=" * 70)
