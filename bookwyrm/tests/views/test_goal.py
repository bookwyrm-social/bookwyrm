""" test for app action functionality """
from unittest.mock import patch
from django.utils import timezone

from django.contrib.auth.models import AnonymousUser
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views


class GoalViews(TestCase):
    """viewing and creating statuses"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.com",
            "mouseword",
            local=True,
            localname="mouse",
            remote_id="https://example.com/users/mouse",
        )
        self.rat = models.User.objects.create_user(
            "rat@local.com",
            "rat@rat.com",
            "ratword",
            local=True,
            localname="rat",
            remote_id="https://example.com/users/rat",
        )
        self.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
        )
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False
        models.SiteSettings.objects.create()

    def test_goal_page_no_goal(self):
        """view a reading goal page for another's unset goal"""
        view = views.Goal.as_view()
        request = self.factory.get("")
        request.user = self.rat

        result = view(request, self.local_user.localname, 2020)
        self.assertEqual(result.status_code, 404)

    def test_goal_page_no_goal_self(self):
        """view a reading goal page for your own unset goal"""
        view = views.Goal.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request, self.local_user.localname, 2020)
        result.render()
        self.assertIsInstance(result, TemplateResponse)

    def test_goal_page_anonymous(self):
        """can't view it without login"""
        view = views.Goal.as_view()
        request = self.factory.get("")
        request.user = self.anonymous_user

        result = view(request, self.local_user.localname, 2020)
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
        result.render()
        self.assertIsInstance(result, TemplateResponse)

    def test_goal_page_private(self):
        """view a user's private goal"""
        models.AnnualGoal.objects.create(
            user=self.local_user, year=2020, goal=15, privacy="followers"
        )
        view = views.Goal.as_view()
        request = self.factory.get("")
        request.user = self.rat

        result = view(request, self.local_user.localname, 2020)
        self.assertEqual(result.status_code, 404)

    @patch("bookwyrm.activitystreams.ActivityStream.add_status")
    def test_create_goal(self, _):
        """create a new goal"""
        view = views.Goal.as_view()
        request = self.factory.post(
            "",
            {
                "user": self.local_user.id,
                "goal": 10,
                "year": 2020,
                "privacy": "unlisted",
                "post-status": True,
            },
        )
        request.user = self.local_user
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            view(request, self.local_user.localname, 2020)

        goal = models.AnnualGoal.objects.get()
        self.assertEqual(goal.user, self.local_user)
        self.assertEqual(goal.goal, 10)
        self.assertEqual(goal.year, 2020)
        self.assertEqual(goal.privacy, "unlisted")

        status = models.GeneratedNote.objects.get()
        self.assertEqual(status.user, self.local_user)
        self.assertEqual(status.privacy, "unlisted")
