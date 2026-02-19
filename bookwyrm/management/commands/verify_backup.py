"""Management command to verify backup integrity.

Provides validation of database and media backups.
"""

import sys
from pathlib import Path
from django.core.management.base import BaseCommand

from bookwyrm.utils.backup import BackupManager


class Command(BaseCommand):
    """Verify backup file integrity."""

    help = "Verify the integrity of backup files"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "backup_path",
            type=str,
            help="Path to backup file to verify",
        )
        parser.add_argument(
            "--backup-type",
            type=str,
            choices=["database", "media", "auto"],
            default="auto",
            help="Type of backup (default: auto-detect)",
        )

    def handle(self, *args, **options):
        """Execute the backup verification command."""
        backup_path = Path(options["backup_path"])
        backup_type = options["backup_type"]

        manager = BackupManager()

        self.stdout.write("=" * 70)
        self.stdout.write(
            self.style.MIGRATE_HEADING("BookWyrm Backup Verification")
        )
        self.stdout.write("=" * 70)
        self.stdout.write("")

        # Auto-detect backup type if needed
        if backup_type == "auto":
            if "db" in backup_path.name or ".dump" in backup_path.name or ".sql" in backup_path.name:
                backup_type = "database"
            elif "media" in backup_path.name:
                backup_type = "media"
            else:
                self.stdout.write(
                    self.style.WARNING(
                        "Could not auto-detect backup type from filename."
                    )
                )
                self.stdout.write(
                    "Please specify --backup-type=[database|media]"
                )
                sys.exit(1)

        self.stdout.write(f"Verifying {backup_type} backup: {backup_path.name}")
        self.stdout.write("")

        # Verify based on type
        if backup_type == "database":
            success, message = manager.verify_database_backup(backup_path)
        else:  # media
            success, message = manager.verify_media_backup(backup_path)

        if success:
            self.stdout.write(self.style.SUCCESS(f"✓ {message}"))
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Backup verification passed"))
        else:
            self.stdout.write(self.style.ERROR(f"✗ {message}"))
            self.stdout.write("")
            self.stdout.write(self.style.ERROR("Backup verification failed"))
            sys.exit(1)

        self.stdout.write("\n" + "=" * 70)
