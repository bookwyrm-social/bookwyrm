"""Tests for Instance Stats admin view"""
from unittest.mock import patch

from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.tests.validate_html import validate_html


class TestInstanceStatsImports(TestCase):
    """Test that the instance stats module imports correctly."""

    def test_instance_stats_view_imports(self):
        """Verify instance stats view module imports without errors"""
        from bookwyrm.views.admin import instance_stats

        self.assertTrue(hasattr(instance_stats, "InstanceStats"))
        self.assertTrue(hasattr(instance_stats, "get_federation_stats"))
        self.assertTrue(hasattr(instance_stats, "get_readwise_stats"))
        self.assertTrue(hasattr(instance_stats, "get_activity_stats"))


@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
class InstanceStatsViewTest(TestCase):
    """Tests for InstanceStats view"""

    @classmethod
    def setUpTestData(cls):
        """Create test admin user"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
        ):
            cls.admin_user = models.User.objects.create_user(
                "admin@local.com",
                "admin@admin.com",
                "adminword",
                local=True,
                localname="admin",
                remote_id="https://example.com/users/admin",
            )
            # Grant admin permissions
            cls.admin_user.groups.add(
                models.Group.objects.get(name="admin")
            )

    def setUp(self):
        """Individual test setup"""
        self.factory = RequestFactory()

    def test_instance_stats_get(self, *_):
        """Test GET request for instance stats page"""
        request = self.factory.get("")
        request.user = self.admin_user
        result = views.InstanceStats.as_view()(request)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_instance_stats_with_interval(self, *_):
        """Test GET request with custom interval"""
        request = self.factory.get("", {"days": "30"})
        request.user = self.admin_user
        result = views.InstanceStats.as_view()(request)
        self.assertEqual(result.status_code, 200)


class InstanceStatsFunctionsTest(TestCase):
    """Tests for the stats helper functions"""

    @classmethod
    def setUpTestData(cls):
        """Create test data"""
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

    def test_get_federation_stats(self):
        """Test federation stats function returns expected structure"""
        from bookwyrm.views.admin.instance_stats import get_federation_stats

        stats = get_federation_stats()
        self.assertIn("federation", stats)
        federation = stats["federation"]
        self.assertIn("total_servers", federation)
        self.assertIn("federated_servers", federation)
        self.assertIn("blocked_servers", federation)
        self.assertIn("remote_users", federation)
        self.assertIn("software_breakdown", federation)

    def test_get_readwise_stats(self):
        """Test readwise stats function returns expected structure"""
        from bookwyrm.views.admin.instance_stats import get_readwise_stats

        stats = get_readwise_stats()
        self.assertIn("readwise", stats)
        readwise = stats["readwise"]
        self.assertIn("users_with_token", readwise)
        self.assertIn("exported_quotes", readwise)
        self.assertIn("total_quotes", readwise)
        self.assertIn("total_imported", readwise)
        self.assertIn("matched_highlights", readwise)
        self.assertIn("unmatched_highlights", readwise)

    def test_get_activity_stats(self):
        """Test activity stats function returns expected structure"""
        from django.utils import timezone
        from bookwyrm.views.admin.instance_stats import get_activity_stats

        now = timezone.now()
        stats = get_activity_stats(now, 7)
        self.assertIn("activity", stats)
        activity = stats["activity"]
        self.assertIn("labels", activity)
        self.assertIn("status_by_day", activity)
        self.assertIn("quotes_by_day", activity)
        self.assertIn("servers_by_day", activity)
        self.assertEqual(len(activity["labels"]), 7)
        self.assertEqual(len(activity["status_by_day"]), 7)
