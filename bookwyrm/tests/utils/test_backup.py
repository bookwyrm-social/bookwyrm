"""Tests for backup utilities"""

import os
import tempfile
from unittest.mock import patch, MagicMock, mock_open
from django.test import TestCase
from bookwyrm.utils.backup import BackupManager


class BackupManagerDatabaseBackupTest(TestCase):
    """Test database backup functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = BackupManager(backup_dir=self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch("bookwyrm.utils.backup.settings")
    @patch("bookwyrm.utils.backup.subprocess.run")
    def test_create_database_backup_custom_format(self, mock_run, mock_settings):
        """Create database backup in custom format"""
        mock_settings.DATABASES = {
            "default": {
                "NAME": "bookwyrm",
                "USER": "bookwyrm",
                "PASSWORD": "password",
                "HOST": "localhost",
                "PORT": "5432",
            }
        }
        mock_run.return_value = MagicMock(returncode=0)

        result = self.manager.create_database_backup(format="custom")
        
        self.assertTrue(result["success"])
        self.assertIn("backup_file", result)
        self.assertTrue(result["backup_file"].endswith(".dump"))
        mock_run.assert_called_once()

    @patch("bookwyrm.utils.backup.settings")
    @patch("bookwyrm.utils.backup.subprocess.run")
    def test_create_database_backup_plain_format(self, mock_run, mock_settings):
        """Create database backup in plain SQL format"""
        mock_settings.DATABASES = {
            "default": {
                "NAME": "bookwyrm",
                "USER": "bookwyrm",
                "PASSWORD": "password",
                "HOST": "localhost",
                "PORT": "5432",
            }
        }
        mock_run.return_value = MagicMock(returncode=0)

        result = self.manager.create_database_backup(format="plain")
        
        self.assertTrue(result["success"])
        self.assertTrue(result["backup_file"].endswith(".sql"))

    @patch("bookwyrm.utils.backup.settings")
    @patch("bookwyrm.utils.backup.subprocess.run")
    def test_create_database_backup_directory_format(self, mock_run, mock_settings):
        """Create database backup in directory format"""
        mock_settings.DATABASES = {
            "default": {
                "NAME": "bookwyrm",
                "USER": "bookwyrm",
                "PASSWORD": "password",
                "HOST": "localhost",
                "PORT": "5432",
            }
        }
        mock_run.return_value = MagicMock(returncode=0)

        result = self.manager.create_database_backup(format="directory")
        
        self.assertTrue(result["success"])
        self.assertTrue(os.path.basename(result["backup_file"]).startswith("bookwyrm_db"))

    @patch("bookwyrm.utils.backup.settings")
    @patch("bookwyrm.utils.backup.subprocess.run")
    def test_create_database_backup_tar_format(self, mock_run, mock_settings):
        """Create database backup in tar format"""
        mock_settings.DATABASES = {
            "default": {
                "NAME": "bookwyrm",
                "USER": "bookwyrm",
                "PASSWORD": "password",
                "HOST": "localhost",
                "PORT": "5432",
            }
        }
        mock_run.return_value = MagicMock(returncode=0)

        result = self.manager.create_database_backup(format="tar")
        
        self.assertTrue(result["success"])
        self.assertTrue(result["backup_file"].endswith(".tar"))

    @patch("bookwyrm.utils.backup.settings")
    @patch("bookwyrm.utils.backup.subprocess.run")
    def test_create_database_backup_no_compress(self, mock_run, mock_settings):
        """Create uncompressed database backup"""
        mock_settings.DATABASES = {
            "default": {
                "NAME": "bookwyrm",
                "USER": "bookwyrm",
                "PASSWORD": "password",
                "HOST": "localhost",
                "PORT": "5432",
            }
        }
        mock_run.return_value = MagicMock(returncode=0)

        result = self.manager.create_database_backup(compress=False)
        
        self.assertTrue(result["success"])
        # Check that compression flag not in command
        args = mock_run.call_args[0][0]
        self.assertNotIn("-Z", args)

    @patch("bookwyrm.utils.backup.settings")
    @patch("bookwyrm.utils.backup.subprocess.run")
    def test_create_database_backup_failure(self, mock_run, mock_settings):
        """Handle database backup failure"""
        mock_settings.DATABASES = {
            "default": {
                "NAME": "bookwyrm",
                "USER": "bookwyrm",
                "PASSWORD": "password",
                "HOST": "localhost",
                "PORT": "5432",
            }
        }
        mock_run.return_value = MagicMock(returncode=1, stderr="Connection refused")

        result = self.manager.create_database_backup()
        
        self.assertFalse(result["success"])
        self.assertIn("error", result)

    @patch("bookwyrm.utils.backup.settings")
    @patch("bookwyrm.utils.backup.subprocess.run")
    def test_create_database_backup_exception(self, mock_run, mock_settings):
        """Handle database backup exception"""
        mock_settings.DATABASES = {
            "default": {
                "NAME": "bookwyrm",
                "USER": "bookwyrm",
                "PASSWORD": "password",
                "HOST": "localhost",
                "PORT": "5432",
            }
        }
        mock_run.side_effect = Exception("pg_dump not found")

        result = self.manager.create_database_backup()
        
        self.assertFalse(result["success"])
        self.assertIn("pg_dump not found", result["error"])


class BackupManagerMediaBackupTest(TestCase):
    """Test media backup functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.media_dir = tempfile.mkdtemp()
        self.manager = BackupManager(backup_dir=self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        if os.path.exists(self.media_dir):
            shutil.rmtree(self.media_dir)

    @patch("bookwyrm.utils.backup.settings")
    def test_create_media_backup(self, mock_settings):
        """Create media backup"""
        mock_settings.MEDIA_ROOT = self.media_dir
        
        # Create test media file
        test_file = os.path.join(self.media_dir, "test.jpg")
        with open(test_file, "w") as f:
            f.write("test content")

        result = self.manager.create_media_backup()
        
        self.assertTrue(result["success"])
        self.assertIn("backup_file", result)
        self.assertTrue(result["backup_file"].endswith(".tar.gz"))
        self.assertTrue(os.path.exists(result["backup_file"]))

    @patch("bookwyrm.utils.backup.settings")
    def test_create_media_backup_empty_directory(self, mock_settings):
        """Create media backup with empty directory"""
        mock_settings.MEDIA_ROOT = self.media_dir

        result = self.manager.create_media_backup()
        
        self.assertTrue(result["success"])
        self.assertTrue(os.path.exists(result["backup_file"]))

    @patch("bookwyrm.utils.backup.settings")
    def test_create_media_backup_nonexistent_directory(self, mock_settings):
        """Handle nonexistent media directory"""
        mock_settings.MEDIA_ROOT = "/nonexistent/directory"

        result = self.manager.create_media_backup()
        
        self.assertFalse(result["success"])
        self.assertIn("error", result)

    @patch("bookwyrm.utils.backup.settings")
    def test_create_media_backup_with_subdirs(self, mock_settings):
        """Create media backup with subdirectories"""
        mock_settings.MEDIA_ROOT = self.media_dir
        
        # Create subdirectory structure
        subdir = os.path.join(self.media_dir, "covers")
        os.makedirs(subdir)
        test_file = os.path.join(subdir, "book_cover.jpg")
        with open(test_file, "w") as f:
            f.write("cover image")

        result = self.manager.create_media_backup()
        
        self.assertTrue(result["success"])
        self.assertTrue(os.path.exists(result["backup_file"]))


class BackupManagerConfigBackupTest(TestCase):
    """Test configuration backup functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = BackupManager(backup_dir=self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch("bookwyrm.utils.backup.settings")
    def test_create_configuration_backup(self, mock_settings):
        """Create configuration backup"""
        # Mock settings
        mock_settings.BASE_DIR = self.temp_dir
        
        # Create test config files
        env_file = os.path.join(self.temp_dir, ".env")
        with open(env_file, "w") as f:
            f.write("SECRET_KEY=test\n")

        result = self.manager.create_configuration_backup()
        
        self.assertTrue(result["success"])
        self.assertIn("backup_file", result)
        self.assertTrue(result["backup_file"].endswith(".tar.gz"))

    @patch("bookwyrm.utils.backup.settings")
    def test_create_configuration_backup_missing_files(self, mock_settings):
        """Handle missing configuration files"""
        mock_settings.BASE_DIR = "/nonexistent"

        result = self.manager.create_configuration_backup()
        
        # Should still succeed even if files don't exist
        self.assertTrue(result["success"])


class BackupManagerFullBackupTest(TestCase):
    """Test full backup functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.media_dir = tempfile.mkdtemp()
        self.manager = BackupManager(backup_dir=self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        if os.path.exists(self.media_dir):
            shutil.rmtree(self.media_dir)

    @patch("bookwyrm.utils.backup.BackupManager.create_database_backup")
    @patch("bookwyrm.utils.backup.BackupManager.create_media_backup")
    @patch("bookwyrm.utils.backup.BackupManager.create_configuration_backup")
    def test_create_full_backup(self, mock_config, mock_media, mock_db):
        """Create full backup with all components"""
        mock_db.return_value = {
            "success": True,
            "backup_file": os.path.join(self.temp_dir, "db.dump"),
        }
        mock_media.return_value = {
            "success": True,
            "backup_file": os.path.join(self.temp_dir, "media.tar.gz"),
        }
        mock_config.return_value = {
            "success": True,
            "backup_file": os.path.join(self.temp_dir, "config.tar.gz"),
        }

        result = self.manager.create_full_backup()
        
        self.assertTrue(result["success"])
        self.assertIn("manifest_file", result)
        self.assertIn("backups", result)
        self.assertEqual(len(result["backups"]), 3)

    @patch("bookwyrm.utils.backup.BackupManager.create_database_backup")
    @patch("bookwyrm.utils.backup.BackupManager.create_media_backup")
    @patch("bookwyrm.utils.backup.BackupManager.create_configuration_backup")
    def test_create_full_backup_partial_failure(self, mock_config, mock_media, mock_db):
        """Handle partial backup failure"""
        mock_db.return_value = {"success": True, "backup_file": "db.dump"}
        mock_media.return_value = {"success": False, "error": "Media backup failed"}
        mock_config.return_value = {"success": True, "backup_file": "config.tar.gz"}

        result = self.manager.create_full_backup()
        
        # Should still succeed with partial backups
        self.assertTrue(result["success"])
        successful_backups = [b for b in result["backups"] if b["success"]]
        self.assertEqual(len(successful_backups), 2)


class BackupManagerListBackupsTest(TestCase):
    """Test backup listing functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = BackupManager(backup_dir=self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_list_backups_empty(self):
        """List backups in empty directory"""
        backups = self.manager.list_backups()
        
        self.assertEqual(len(backups), 0)

    def test_list_backups_with_files(self):
        """List existing backup files"""
        # Create test backup files
        backup1 = os.path.join(self.temp_dir, "bookwyrm_db_20240101.dump")
        backup2 = os.path.join(self.temp_dir, "bookwyrm_media_20240101.tar.gz")
        
        with open(backup1, "w") as f:
            f.write("backup1")
        with open(backup2, "w") as f:
            f.write("backup2")

        backups = self.manager.list_backups()
        
        self.assertEqual(len(backups), 2)
        self.assertTrue(any("bookwyrm_db" in b["filename"] for b in backups))

    def test_list_backups_with_sizes(self):
        """List backups with file sizes"""
        backup_file = os.path.join(self.temp_dir, "test_backup.dump")
        with open(backup_file, "w") as f:
            f.write("a" * 1024)  # 1 KB

        backups = self.manager.list_backups()
        
        self.assertGreater(len(backups), 0)
        self.assertIn("size", backups[0])


class BackupManagerVerifyTest(TestCase):
    """Test backup verification functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = BackupManager(backup_dir=self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch("bookwyrm.utils.backup.subprocess.run")
    def test_verify_database_backup(self, mock_run):
        """Verify database backup"""
        backup_file = os.path.join(self.temp_dir, "test_backup.dump")
        with open(backup_file, "w") as f:
            f.write("test")
        
        mock_run.return_value = MagicMock(returncode=0)

        result = self.manager.verify_database_backup(backup_file)
        
        self.assertTrue(result["valid"])

    @patch("bookwyrm.utils.backup.subprocess.run")
    def test_verify_database_backup_invalid(self, mock_run):
        """Verify invalid database backup"""
        backup_file = os.path.join(self.temp_dir, "test_backup.dump")
        with open(backup_file, "w") as f:
            f.write("test")
        
        mock_run.return_value = MagicMock(returncode=1, stderr="Invalid format")

        result = self.manager.verify_database_backup(backup_file)
        
        self.assertFalse(result["valid"])
        self.assertIn("error", result)

    def test_verify_database_backup_nonexistent(self):
        """Handle nonexistent backup file"""
        result = self.manager.verify_database_backup("/nonexistent/file.dump")
        
        self.assertFalse(result["valid"])
        self.assertIn("error", result)

    def test_verify_media_backup(self):
        """Verify media backup"""
        import tarfile
        
        backup_file = os.path.join(self.temp_dir, "test_media.tar.gz")
        with tarfile.open(backup_file, "w:gz") as tar:
            # Create empty tar file
            pass

        result = self.manager.verify_media_backup(backup_file)
        
        self.assertTrue(result["valid"])

    def test_verify_media_backup_invalid(self):
        """Verify invalid media backup"""
        backup_file = os.path.join(self.temp_dir, "invalid.tar.gz")
        with open(backup_file, "w") as f:
            f.write("not a tar file")

        result = self.manager.verify_media_backup(backup_file)
        
        self.assertFalse(result["valid"])


class BackupManagerCleanupTest(TestCase):
    """Test backup cleanup functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = BackupManager(backup_dir=self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_cleanup_old_backups(self):
        """Clean up old backup files"""
        import datetime
        from pathlib import Path
        
        # Create old backup file
        old_backup = os.path.join(self.temp_dir, "old_backup.dump")
        with open(old_backup, "w") as f:
            f.write("old")
        
        # Set modification time to 31 days ago
        old_time = (datetime.datetime.now() - datetime.timedelta(days=31)).timestamp()
        os.utime(old_backup, (old_time, old_time))
        
        # Create recent backup
        recent_backup = os.path.join(self.temp_dir, "recent_backup.dump")
        with open(recent_backup, "w") as f:
            f.write("recent")

        result = self.manager.cleanup_old_backups(max_age_days=30)
        
        self.assertTrue(result["success"])
        self.assertGreater(result["deleted_count"], 0)
        self.assertFalse(os.path.exists(old_backup))
        self.assertTrue(os.path.exists(recent_backup))

    def test_cleanup_old_backups_none(self):
        """No backups to clean up"""
        result = self.manager.cleanup_old_backups()
        
        self.assertTrue(result["success"])
        self.assertEqual(result["deleted_count"], 0)


class BackupManagerIntegrationTest(TestCase):
    """Integration tests for backup manager"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.media_dir = tempfile.mkdtemp()
        self.manager = BackupManager(backup_dir=self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        if os.path.exists(self.media_dir):
            shutil.rmtree(self.media_dir)

    @patch("bookwyrm.utils.backup.settings")
    @patch("bookwyrm.utils.backup.subprocess.run")
    def test_backup_and_verify_workflow(self, mock_run, mock_settings):
        """Test complete backup and verify workflow"""
        mock_settings.DATABASES = {
            "default": {
                "NAME": "bookwyrm",
                "USER": "bookwyrm",
                "PASSWORD": "password",
                "HOST": "localhost",
                "PORT": "5432",
            }
        }
        mock_settings.MEDIA_ROOT = self.media_dir
        mock_run.return_value = MagicMock(returncode=0)

        # Create backup
        backup_result = self.manager.create_database_backup()
        self.assertTrue(backup_result["success"])
        
        # Verify backup
        verify_result = self.manager.verify_database_backup(backup_result["backup_file"])
        self.assertTrue(verify_result["valid"])

    @patch("bookwyrm.utils.backup.settings")
    def test_list_and_cleanup_workflow(self, mock_settings):
        """Test list and cleanup workflow"""
        # Create test backups
        for i in range(3):
            backup_file = os.path.join(self.temp_dir, f"backup_{i}.dump")
            with open(backup_file, "w") as f:
                f.write(f"backup {i}")
        
        # List backups
        backups = self.manager.list_backups()
        self.assertEqual(len(backups), 3)
        
        # Cleanup (with max_age_days=0 to delete all)
        result = self.manager.cleanup_old_backups(max_age_days=0)
        self.assertEqual(result["deleted_count"], 3)
        
        # List again
        backups = self.manager.list_backups()
        self.assertEqual(len(backups), 0)
