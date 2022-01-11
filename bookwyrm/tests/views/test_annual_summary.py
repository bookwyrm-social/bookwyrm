"""testing the annual summary page"""
from datetime import datetime
from unittest.mock import patch
import pytz

from django.contrib.auth.models import AnonymousUser
from django.http import Http404
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.tests.validate_html import validate_html


def make_date(*args):
    """helper function to easily generate a date obj"""
    return datetime(*args, tzinfo=pytz.UTC)


class AnnualSummary(TestCase):
    """views"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.com",
                "mouseword",
                local=True,
                localname="mouse",
                remote_id="https://example.com/users/mouse",
                summary_keys={"2020": "0123456789"},
            )
        self.work = models.Work.objects.create(title="Test Work")
        self.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=self.work,
            pages=300,
        )

        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False

        self.year = "2020"
        models.SiteSettings.objects.create()

    def test_annual_summary_not_authenticated(self, *_):
        """there are so many views, this just makes sure it DOESN’T LOAD"""
        view = views.AnnualSummary.as_view()
        request = self.factory.get("")
        request.user = self.anonymous_user

        with self.assertRaises(Http404):
            view(request, self.local_user.localname, self.year)

    def test_annual_summary_not_authenticated_with_key(self, *_):
        """there are so many views, this just makes sure it DOES LOAD"""
        key = self.local_user.summary_keys[self.year]
        view = views.AnnualSummary.as_view()
        request_url = (
            f"user/{self.local_user.localname}/{self.year}-in-the-books?key={key}"
        )
        request = self.factory.get(request_url)
        request.user = self.anonymous_user

        result = view(request, self.local_user.localname, self.year)

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_annual_summary_wrong_year(self, *_):
        """there are so many views, this just makes sure it DOESN’T LOAD"""
        view = views.AnnualSummary.as_view()
        request = self.factory.get("")
        request.user = self.anonymous_user

        with self.assertRaises(Http404):
            view(request, self.local_user.localname, self.year)

    def test_annual_summary_empty_page(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.AnnualSummary.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request, self.local_user.localname, self.year)

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    @patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
    @patch("bookwyrm.activitystreams.add_book_statuses_task.delay")
    def test_annual_summary_page(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        models.ReadThrough.objects.create(
            user=self.local_user, book=self.book, finish_date=make_date(2020, 1, 1)
        )

        view = views.AnnualSummary.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request, self.local_user.localname, self.year)

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    @patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
    @patch("bookwyrm.activitystreams.add_book_statuses_task.delay")
    def test_annual_summary_page_with_review(self, *_):
        """there are so many views, this just makes sure it LOADS"""

        models.Review.objects.create(
            name="Review name",
            content="test content",
            rating=3.0,
            user=self.local_user,
            book=self.book,
        )

        models.ReadThrough.objects.create(
            user=self.local_user, book=self.book, finish_date=make_date(2020, 1, 1)
        )

        view = views.AnnualSummary.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request, self.local_user.localname, self.year)

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)
