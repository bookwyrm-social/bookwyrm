""" test for app action functionality """
from unittest.mock import patch

from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory
from django.http.response import Http404
from bookwyrm import models, views
from bookwyrm.tests.validate_html import validate_html


class SeriesViews(TestCase):
    """series views"""

    @classmethod
    def setUpTestData(cls):
        """we need basic test data and mocks"""

        cls.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.com",
            "mouseword"
        )

        cls.book = models.Work.objects.create(title="test book")
        cls.series = models.Series.objects.create(name="test series", user=cls.local_user)
        cls.seriesbook = models.SeriesBook.objects.create(book=cls.book, series=cls.series, user=cls.local_user)

        models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    def test_series_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Series.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request, self.series.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())

        self.assertEqual(result.status_code, 200)


    def test_editseries_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.EditSeries.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request, self.series.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())

        self.assertEqual(result.status_code, 200)


    def test_seriesbook_page_404s(self):
        """make sure it doesn't load for normal traffic"""
        view = views.SeriesBook.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        with self.assertRaises(Http404):
            result = view(request, self.seriesbook.id)

