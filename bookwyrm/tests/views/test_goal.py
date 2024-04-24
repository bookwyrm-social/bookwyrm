""" test for app action functionality """
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.http import Http404
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory
from django.utils import timezone

from bookwyrm import models, views
from bookwyrm.tests.validate_html import validate_html


class GoalViews(TestCase):
    """viewing and creating statuses"""

    @classmethod
    def setUpTestData(cls):
        """we need basic test data and mocks"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.com",
                "mouseword",
                local=True,
                localname="mouse",
                remote_id="https://example.com/users/mouse",
            )
            cls.rat = models.User.objects.create_user(
                "rat@local.com",
                "rat@rat.com",
                "ratword",
                local=True,
                localname="rat",
                remote_id="https://example.com/users/rat",
            )
        cls.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
        )
        models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.year = timezone.now().year
        self.factory = RequestFactory()
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False

    def test_goal_page_no_goal(self):
        """view a reading goal page for another's unset goal"""
        view = views.Goal.as_view()
        request = self.factory.get("")
        request.user = self.rat

        result = view(request, self.local_user.localname, self.year)
        self.assertEqual(result.status_code, 404)

    def test_goal_page_no_goal_self(self):
        """view a reading goal page for your own unset goal"""
        view = views.Goal.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request, self.local_user.localname, self.year)
        validate_html(result.render())
        self.assertIsInstance(result, TemplateResponse)

    def test_goal_page_anonymous(self):
        """can't view it without login"""
        view = views.Goal.as_view()
        request = self.factory.get("")
        request.user = self.anonymous_user

        result = view(request, self.local_user.localname, self.year)
        self.assertEqual(result.status_code, 302)

    def test_goal_page_public(self):
        """view a user's public goal"""
        models.ReadThrough.objects.create(
            finish_date=timezone.now(),
            user=self.local_user,
            book=self.book,
        )

        models.AnnualGoal.objects.create(
            user=self.local_user,
            year=timezone.now().year,
            goal=128937123,
            privacy="public",
        )
        view = views.Goal.as_view()
        request = self.factory.get("")
        request.user = self.rat

        result = view(request, self.local_user.localname, timezone.now().year)
        validate_html(result.render())
        self.assertIsInstance(result, TemplateResponse)

    def test_goal_page_private(self):
        """view a user's private goal"""
        models.AnnualGoal.objects.create(
            user=self.local_user, year=self.year, goal=15, privacy="followers"
        )
        view = views.Goal.as_view()
        request = self.factory.get("")
        request.user = self.rat

        with self.assertRaises(Http404):
            view(request, self.local_user.localname, self.year)

    @patch("bookwyrm.activitystreams.add_status_task.delay")
    def test_create_goal(self, _):
        """create a new goal"""
        view = views.Goal.as_view()
        request = self.factory.post(
            "",
            {
                "user": self.local_user.id,
                "goal": 10,
                "year": self.year,
                "privacy": "unlisted",
                "post-status": True,
            },
        )
        request.user = self.local_user
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            view(request, self.local_user.localname, self.year)

        goal = models.AnnualGoal.objects.get()
        self.assertEqual(goal.user, self.local_user)
        self.assertEqual(goal.goal, 10)
        self.assertEqual(goal.year, self.year)
        self.assertEqual(goal.privacy, "unlisted")

        status = models.GeneratedNote.objects.get()
        self.assertEqual(status.user, self.local_user)
        self.assertEqual(status.privacy, "unlisted")
