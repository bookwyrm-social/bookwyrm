"""Tests for Readwise integration views"""
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views, forms
from bookwyrm.tests.validate_html import validate_html


class TestReadwiseImports(TestCase):
    """Test that all Readwise modules import correctly.

    These tests catch import errors, syntax errors, and undefined variables
    before they reach production.
    """

    def test_readwise_view_imports(self):
        """Verify readwise view module imports without errors"""
        # This will fail if there are import errors or syntax issues
        from bookwyrm.views.preferences import readwise

        # Verify key components exist
        self.assertTrue(hasattr(readwise, 'ReadwiseSettings'))
        self.assertTrue(hasattr(readwise, '_'))  # Translation function
        self.assertTrue(hasattr(readwise, 'messages'))

    def test_readwise_connector_imports(self):
        """Verify readwise connector module imports without errors"""
        from bookwyrm.connectors import readwise

        # Verify key components exist
        self.assertTrue(hasattr(readwise, 'ReadwiseClient'))
        self.assertTrue(hasattr(readwise, 'export_quote_to_readwise'))
        self.assertTrue(hasattr(readwise, 'export_all_quotes_to_readwise'))
        self.assertTrue(hasattr(readwise, 'import_readwise_highlights'))

    def test_readwise_models_imports(self):
        """Verify readwise models import without errors"""
        from bookwyrm.models import readwise

        # Verify key components exist
        self.assertTrue(hasattr(readwise, 'ReadwiseSync'))
        self.assertTrue(hasattr(readwise, 'ReadwiseSyncedHighlight'))

    def test_readwise_form_imports(self):
        """Verify readwise form imports without errors"""
        # Verify form exists in forms module
        self.assertTrue(hasattr(forms, 'ReadwiseSettingsForm'))


@patch("bookwyrm.activitystreams.add_book_statuses_task.delay")
@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
class ReadwiseSettingsViewTest(TestCase):
    """Tests for ReadwiseSettings view"""

    @classmethod
    def setUpTestData(cls):
        """Create test user"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
        ):
            cls.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.com",
                "mouseword",
                local=True,
                localname="mouse",
                remote_id="https://example.com/users/mouse",
            )

    def setUp(self):
        """Individual test setup"""
        self.factory = RequestFactory()

    def test_readwise_get_no_token(self, *_):
        """Test GET request without token configured"""
        request = self.factory.get("")
        request.user = self.local_user
        result = views.ReadwiseSettings.as_view()(request)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_readwise_get_with_token(self, *_):
        """Test GET request with token configured"""
        self.local_user.readwise_token = "test_token"
        self.local_user.save()

        request = self.factory.get("")
        request.user = self.local_user
        result = views.ReadwiseSettings.as_view()(request)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        # Clean up
        self.local_user.readwise_token = None
        self.local_user.save()

    def test_readwise_save_settings(self, *_):
        """Test saving Readwise settings"""
        request = self.factory.post("", {
            "readwise_token": "new_test_token",
            "readwise_auto_export": True,
        })
        request.user = self.local_user

        result = views.ReadwiseSettings.as_view()(request)

        # Should redirect after successful save
        self.assertEqual(result.status_code, 302)

        # Verify settings were saved
        self.local_user.refresh_from_db()
        self.assertEqual(self.local_user.readwise_token, "new_test_token")
        self.assertTrue(self.local_user.readwise_auto_export)

        # Clean up
        self.local_user.readwise_token = None
        self.local_user.readwise_auto_export = False
        self.local_user.save()

    def test_readwise_export_without_token(self, *_):
        """Test export action without token fails gracefully"""
        request = self.factory.post("", {"action": "export"})
        request.user = self.local_user

        result = views.ReadwiseSettings.as_view()(request)

        # Should redirect with error message
        self.assertEqual(result.status_code, 302)

    @patch("bookwyrm.connectors.readwise.export_all_quotes_to_readwise.delay")
    def test_readwise_export_with_token(self, mock_export, *_):
        """Test export action with token triggers async task"""
        self.local_user.readwise_token = "test_token"
        self.local_user.save()

        request = self.factory.post("", {"action": "export"})
        request.user = self.local_user

        # Use transaction.on_commit callback
        from django.test import override_settings
        with self.captureOnCommitCallbacks(execute=True):
            result = views.ReadwiseSettings.as_view()(request)

        self.assertEqual(result.status_code, 302)
        mock_export.assert_called_once_with(self.local_user.id)

        # Clean up
        self.local_user.readwise_token = None
        self.local_user.save()

    def test_readwise_import_without_token(self, *_):
        """Test import action without token fails gracefully"""
        request = self.factory.post("", {"action": "import"})
        request.user = self.local_user

        result = views.ReadwiseSettings.as_view()(request)

        # Should redirect with error message
        self.assertEqual(result.status_code, 302)

    @patch("bookwyrm.connectors.readwise.import_readwise_highlights.delay")
    def test_readwise_import_with_token(self, mock_import, *_):
        """Test import action with token triggers async task"""
        self.local_user.readwise_token = "test_token"
        self.local_user.save()

        request = self.factory.post("", {"action": "import"})
        request.user = self.local_user

        # Use transaction.on_commit callback
        with self.captureOnCommitCallbacks(execute=True):
            result = views.ReadwiseSettings.as_view()(request)

        self.assertEqual(result.status_code, 302)
        mock_import.assert_called_once_with(self.local_user.id)

        # Clean up
        self.local_user.readwise_token = None
        self.local_user.save()


class ReadwiseModelsTest(TestCase):
    """Tests for Readwise models"""

    @classmethod
    def setUpTestData(cls):
        """Create test user"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
        ):
            cls.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.com",
                "mouseword",
                local=True,
                localname="mouse",
                remote_id="https://example.com/users/mouse",
            )

    def test_readwise_sync_creation(self):
        """Test ReadwiseSync model creation"""
        sync = models.ReadwiseSync.objects.create(user=self.local_user)
        self.assertEqual(sync.user, self.local_user)
        self.assertIsNone(sync.last_export_at)
        self.assertIsNone(sync.last_import_at)

    def test_readwise_sync_unique_per_user(self):
        """Test only one ReadwiseSync per user"""
        models.ReadwiseSync.objects.create(user=self.local_user)

        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            models.ReadwiseSync.objects.create(user=self.local_user)

    def test_readwise_synced_highlight_creation(self):
        """Test ReadwiseSyncedHighlight model creation"""
        highlight = models.ReadwiseSyncedHighlight.objects.create(
            user=self.local_user,
            readwise_id=12345,
            book_title="Test Book",
            highlight_text="Test highlight text",
        )
        self.assertEqual(highlight.user, self.local_user)
        self.assertEqual(highlight.readwise_id, 12345)
        self.assertIsNone(highlight.quotation)

    def test_readwise_synced_highlight_unique_constraint(self):
        """Test unique constraint on user + readwise_id"""
        models.ReadwiseSyncedHighlight.objects.create(
            user=self.local_user,
            readwise_id=12345,
            book_title="Test Book",
            highlight_text="Test highlight",
        )

        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            models.ReadwiseSyncedHighlight.objects.create(
                user=self.local_user,
                readwise_id=12345,  # Same ID
                book_title="Another Book",
                highlight_text="Another highlight",
            )
