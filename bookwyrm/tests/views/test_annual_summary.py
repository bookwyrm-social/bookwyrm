"""testing the annual summary page"""
from datetime import datetime
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.http import Http404
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.tests.validate_html import validate_html


class AnnualSummary(TestCase):
    """views"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
            self.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.com",
                "mouseword",
                local=True,
                localname="mouse",
                remote_id="https://example.com/users/mouse",
            )
        self.work = models.Work.objects.create(title="Test Work")
        self.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=self.work,
            pages=300,
        )
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
          self.review = models.Review.objects.create(
              name="Review name",
              content="test content",
              rating=3.0,
              user=self.local_user,
              book=self.book,
          )
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False

        self.year = 2020
        models.SiteSettings.objects.create()

    def test_annual_summary_not_authenticated(self, *_):
        """there are so many views, this just makes sure it DOESN’T LOAD"""
        view = views.AnnualSummary.as_view()
        request = self.factory.get("")
        request.user = self.anonymous_user

        with patch(
            "bookwyrm.views.annual_summary.is_year_available"
        ) as is_year_available:
            is_year_available.return_value = True
            with self.assertRaises(Http404):
                view(request, self.year)

    def test_annual_summary_wrong_year(self, *_):
        """there are so many views, this just makes sure it DOESN’T LOAD"""
        view = views.AnnualSummary.as_view()
        request = self.factory.get("")
        request.user = self.anonymous_user

        with patch(
            "bookwyrm.views.annual_summary.is_year_available"
        ) as is_year_available:
            is_year_available.return_value = False
            with self.assertRaises(Http404):
                view(request, self.year)

    def test_annual_summary_empty_page(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.AnnualSummary.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        with patch(
            "bookwyrm.views.annual_summary.is_year_available"
        ) as is_year_available:
            is_year_available.return_value = True
            result = view(request, self.year)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_annual_summary_page(self, *_):
        """there are so many views, this just makes sure it LOADS"""

        shelf = self.local_user.shelf_set.get(identifier="read")

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            models.ShelfBook.objects.create(
                book=self.book,
                user=self.local_user,
                shelf=shelf,
                shelved_date=datetime(2020, 1, 1),
            )

        view = views.AnnualSummary.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        with patch(
            "bookwyrm.views.annual_summary.is_year_available"
        ) as is_year_available:
            is_year_available.return_value = True
            result = view(request, self.year)

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)
