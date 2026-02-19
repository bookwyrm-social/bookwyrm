"""Backup and recovery utilities for BookWyrm.

Provides tools for backing up database, media files, and configuration,
as well as verifying backups and restoring from backups.
"""

import gzip
import json
import logging
import os
import shutil
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from django.core.management import call_command
from django.db import connection

logger = logging.getLogger(__name__)


class BackupManager:
    """Manages backups of database, media, and configuration."""

    def __init__(self, backup_dir: Optional[str] = None):
        """Initialize backup manager.

        Args:
            backup_dir: Directory to store backups (default: 'backups' in BASE_DIR)
        """
        if backup_dir:
            self.backup_dir = Path(backup_dir)
        else:
            self.backup_dir = Path(settings.BASE_DIR) / "backups"

        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_database_backup(
        self, compress: bool = True, format: str = "custom"
    ) -> Tuple[bool, str, Optional[Path]]:
        """Create a database backup using pg_dump.

        Args:
            compress: Whether to compress the backup
            format: Backup format ('custom', 'plain', 'directory', 'tar')

        Returns:
            Tuple of (success, message, backup_path)
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bookwyrm_db_{timestamp}"

            if format == "custom":
                filename += ".dump"
            elif format == "plain":
                filename += ".sql"
            elif format == "directory":
                filename = filename  # No extension for directory format
            else:  # tar
                filename += ".tar"

            if compress and format == "plain":
                filename += ".gz"

            backup_path = self.backup_dir / filename

            # Get database connection info
            db_config = settings.DATABASES["default"]
            
            # Prepare pg_dump command
            env = os.environ.copy()
            env["PGPASSWORD"] = db_config.get("PASSWORD", "")

            cmd = [
                "pg_dump",
                "-h", db_config.get("HOST", "localhost"),
                "-p", str(db_config.get("PORT", 5432)),
                "-U", db_config.get("USER", "postgres"),
                "-d", db_config["NAME"],
                "-F", format[0],  # Format: c=custom, p=plain, d=directory, t=tar
            ]

            if format != "directory":
                cmd.extend(["-f", str(backup_path)])
            else:
                backup_path.mkdir(parents=True, exist_ok=True)
                cmd.extend(["-f", str(backup_path)])

            # Run pg_dump
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                return False, f"pg_dump failed: {result.stderr}", None

            # Compress if using plain format and compression requested
            if compress and format == "plain":
                with open(backup_path.with_suffix(""), "rb") as f_in:
                    with gzip.open(backup_path, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.remove(backup_path.with_suffix(""))

            size_mb = self._get_size_mb(backup_path)
            return (
                True,
                f"Database backup created: {backup_path.name} ({size_mb:.2f} MB)",
                backup_path,
            )

        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            return False, f"Database backup failed: {str(e)}", None

    def create_media_backup(self, compress: bool = True) -> Tuple[bool, str, Optional[Path]]:
        """Create a backup of media files.

        Args:
            compress: Whether to compress the backup

        Returns:
            Tuple of (success, message, backup_path)
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bookwyrm_media_{timestamp}.tar"
            
            if compress:
                filename += ".gz"

            backup_path = self.backup_dir / filename

            # Get media root
            media_root = Path(settings.MEDIA_ROOT)

            if not media_root.exists():
                return False, "Media directory does not exist", None

            # Create tar archive
            mode = "w:gz" if compress else "w"
            
            with tarfile.open(backup_path, mode) as tar:
                tar.add(media_root, arcname="media")

            size_mb = self._get_size_mb(backup_path)
            return (
                True,
                f"Media backup created: {backup_path.name} ({size_mb:.2f} MB)",
                backup_path,
            )

        except Exception as e:
            logger.error(f"Media backup failed: {e}")
            return False, f"Media backup failed: {str(e)}", None

    def create_configuration_backup(self) -> Tuple[bool, str, Optional[Path]]:
        """Create a backup of configuration files.

        Returns:
            Tuple of (success, message, backup_path)
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bookwyrm_config_{timestamp}.tar.gz"
            backup_path = self.backup_dir / filename

            base_dir = Path(settings.BASE_DIR)

            # Files to backup
            config_files = [
                ".env",
                ".env.prod",
                "docker-compose.yml",
                "nginx/default.conf",
            ]

            with tarfile.open(backup_path, "w:gz") as tar:
                for config_file in config_files:
                    file_path = base_dir / config_file
                    if file_path.exists():
                        tar.add(file_path, arcname=config_file)

            size_mb = self._get_size_mb(backup_path)
            return (
                True,
                f"Configuration backup created: {backup_path.name} ({size_mb:.2f} MB)",
                backup_path,
            )

        except Exception as e:
            logger.error(f"Configuration backup failed: {e}")
            return False, f"Configuration backup failed: {str(e)}", None

    def create_full_backup(self, compress: bool = True) -> Dict:
        """Create a complete backup of database, media, and configuration.

        Args:
            compress: Whether to compress backups

        Returns:
            Dictionary with backup results
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "database": {},
            "media": {},
            "configuration": {},
            "success": True,
        }

        # Database backup
        db_success, db_msg, db_path = self.create_database_backup(compress=compress)
        results["database"] = {
            "success": db_success,
            "message": db_msg,
            "path": str(db_path) if db_path else None,
        }
        if not db_success:
            results["success"] = False

        # Media backup
        media_success, media_msg, media_path = self.create_media_backup(compress=compress)
        results["media"] = {
            "success": media_success,
            "message": media_msg,
            "path": str(media_path) if media_path else None,
        }
        if not media_success:
            results["success"] = False

        # Configuration backup
        config_success, config_msg, config_path = self.create_configuration_backup()
        results["configuration"] = {
            "success": config_success,
            "message": config_msg,
            "path": str(config_path) if config_path else None,
        }
        if not config_success:
            results["success"] = False

        # Create manifest
        manifest_path = self.backup_dir / f"backup_manifest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(manifest_path, "w") as f:
            json.dump(results, f, indent=2)

        results["manifest_path"] = str(manifest_path)

        return results

    def list_backups(self) -> List[Dict]:
        """List all backups in the backup directory.

        Returns:
            List of backup information dictionaries
        """
        backups = []

        if not self.backup_dir.exists():
            return backups

        for item in self.backup_dir.iterdir():
            if item.is_file():
                backup_type = "unknown"
                if "db" in item.name:
                    backup_type = "database"
                elif "media" in item.name:
                    backup_type = "media"
                elif "config" in item.name:
                    backup_type = "configuration"
                elif "manifest" in item.name:
                    backup_type = "manifest"

                backups.append({
                    "name": item.name,
                    "type": backup_type,
                    "path": str(item),
                    "size_mb": self._get_size_mb(item),
                    "created": datetime.fromtimestamp(item.stat().st_mtime).isoformat(),
                })

        return sorted(backups, key=lambda x: x["created"], reverse=True)

    def verify_database_backup(self, backup_path: Path) -> Tuple[bool, str]:
        """Verify a database backup by testing restoration (dry run).

        Args:
            backup_path: Path to backup file

        Returns:
            Tuple of (success, message)
        """
        try:
            # Basic file checks
            if not backup_path.exists():
                return False, "Backup file does not exist"

            if backup_path.stat().st_size == 0:
                return False, "Backup file is empty"

            # Try to read the backup file to check if it's valid
            if backup_path.suffix == ".gz":
                # Try to open gzipped file
                try:
                    with gzip.open(backup_path, "rb") as f:
                        f.read(1024)  # Read first 1KB
                except Exception as e:
                    return False, f"Invalid gzip file: {str(e)}"
            elif backup_path.suffix == ".dump":
                # Check if it's a valid pg_dump custom format
                try:
                    with open(backup_path, "rb") as f:
                        header = f.read(5)
                        if header != b"PGDMP":
                            return False, "Invalid pg_dump custom format file"
                except Exception as e:
                    return False, f"Cannot read backup file: {str(e)}"

            return True, "Backup file appears valid"

        except Exception as e:
            logger.error(f"Backup verification failed: {e}")
            return False, f"Verification failed: {str(e)}"

    def verify_media_backup(self, backup_path: Path) -> Tuple[bool, str]:
        """Verify a media backup.

        Args:
            backup_path: Path to backup file

        Returns:
            Tuple of (success, message)
        """
        try:
            if not backup_path.exists():
                return False, "Backup file does not exist"

            if backup_path.stat().st_size == 0:
                return False, "Backup file is empty"

            # Try to open the tar file
            try:
                with tarfile.open(backup_path, "r:*") as tar:
                    members = tar.getmembers()
                    if len(members) == 0:
                        return False, "Backup archive is empty"

                return True, f"Backup contains {len(members)} file(s)"

            except Exception as e:
                return False, f"Invalid tar file: {str(e)}"

        except Exception as e:
            logger.error(f"Media backup verification failed: {e}")
            return False, f"Verification failed: {str(e)}"

    def cleanup_old_backups(self, keep_count: int = 10) -> Tuple[int, int]:
        """Delete old backups, keeping only the most recent ones.

        Args:
            keep_count: Number of recent backups to keep per type

        Returns:
            Tuple of (deleted_count, size_freed_mb)
        """
        backups = self.list_backups()

        # Group by type
        by_type = {}
        for backup in backups:
            backup_type = backup["type"]
            if backup_type not in by_type:
                by_type[backup_type] = []
            by_type[backup_type].append(backup)

        deleted_count = 0
        size_freed = 0

        # Delete old backups for each type
        for backup_type, type_backups in by_type.items():
            if len(type_backups) > keep_count:
                to_delete = type_backups[keep_count:]
                for backup in to_delete:
                    try:
                        Path(backup["path"]).unlink()
                        deleted_count += 1
                        size_freed += backup["size_mb"]
                    except Exception as e:
                        logger.error(f"Failed to delete backup {backup['name']}: {e}")

        return deleted_count, size_freed

    def _get_size_mb(self, path: Path) -> float:
        """Get file or directory size in megabytes.

        Args:
            path: Path to file or directory

        Returns:
            Size in MB
        """
        if path.is_file():
            return path.stat().st_size / (1024 * 1024)
        elif path.is_dir():
            total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
            return total / (1024 * 1024)
        return 0.0
