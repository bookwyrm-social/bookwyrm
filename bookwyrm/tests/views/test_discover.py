""" test for app action functionality """
from unittest.mock import patch
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models
from bookwyrm import views


class DiscoverViews(TestCase):
    """pages you land on without really trying"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
            self.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.mouse",
                "password",
                local=True,
                localname="mouse",
            )
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False
        models.SiteSettings.objects.create()

    def test_discover_page_empty(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Discover.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        with patch(
            "bookwyrm.activitystreams.ActivityStream.get_activity_stream"
        ) as mock:
            result = view(request)
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(result.status_code, 200)
        result.render()

    @patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay")
    @patch("bookwyrm.activitystreams.add_status_task.delay")
    def test_discover_page(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Discover.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        book = models.Edition.objects.create(
            title="hi", parent_work=models.Work.objects.create(title="work")
        )

        models.Comment.objects.create(
            book=book,
            user=self.local_user,
            content="hello",
        )
        models.Status.objects.create(user=self.local_user, content="beep")

        with patch(
            "bookwyrm.activitystreams.ActivityStream.get_activity_stream"
        ) as mock:
            mock.return_value = models.Status.objects.all()
            result = view(request)
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(result.status_code, 200)
        result.render()

    def test_discover_page_logged_out(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Discover.as_view()
        request = self.factory.get("")
        request.user = self.anonymous_user
        result = view(request)
        self.assertEqual(result.status_code, 302)
