"""test for app action functionality"""

from unittest.mock import patch
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory
from django.http.response import Http404
from bookwyrm import models, views, forms
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.tests.validate_html import validate_html


class SeriesViews(TestCase):
    """series views"""

    @classmethod
    def setUpTestData(cls):
        """we need basic test data and mocks"""

        cls.user = models.User.objects.create_user(
            "instance",
            "instance@example.example",
            "pass",
            local=True,
            localname="instance",
        )

        cls.group = Group.objects.create(name="editor")
        cls.group.permissions.add(
            Permission.objects.create(
                name="edit_book",
                codename="edit_book",
                content_type=ContentType.objects.get_for_model(models.User),
            ).id
        )

        cls.book = models.Work.objects.create(title="test book")
        cls.series = models.Series.objects.create(
            user=cls.user, name="test series", remote_id="https://example.com/series/1"
        )
        cls.seriesbook = models.SeriesBook.objects.create(
            book=cls.book,
            series=cls.series,
            user=cls.user,
            remote_id="https://example.com/seriesbook/1",
        )

        models.SiteSettings.objects.get_or_create()

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    def test_series_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Series.as_view()
        request = self.factory.get("")
        request.user = self.user
        result = view(request, self.series.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())

        self.assertEqual(result.status_code, 200)

    def test_editseries_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.EditSeries.as_view()
        request = self.factory.get("")
        request.user = self.user
        result = view(request, self.series.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())

        self.assertEqual(result.status_code, 200)

    def test_post_editseries_page(self):
        """posting edit data"""

        self.assertEqual(self.seriesbook.series_number, None)
        self.assertEqual(len(self.series.alternative_names), 0)

        view = views.EditSeries.as_view()
        form = forms.SeriesForm(instance=self.series)
        form.data["user"] = self.user.id
        form.data["name"] = "New Series Name"
        form.data["alternative_names"] = ["beep", "boop"]
        form.data[f"series_number-{self.book.id}"] = "99"
        request = self.factory.post("", form.data)

        self.user.groups.add(self.group)
        request.user = self.user

        view(request, self.series.id)
        self.series.refresh_from_db()
        self.seriesbook.refresh_from_db()

        self.assertEqual(self.series.name, "New Series Name")
        self.assertEqual(len(self.series.alternative_names), 2)
        self.assertEqual(self.series.alternative_names[0], "beep")
        self.assertEqual(self.series.alternative_names[1], "boop")
        self.assertEqual(self.seriesbook.series_number, "99")

    def test_seriesbook_page_404s(self):
        """make sure it doesn't load for normal traffic"""
        view = views.SeriesBook.as_view()
        request = self.factory.get("")
        request.user = self.user

        with self.assertRaises(Http404):
            view(request, self.seriesbook.id)

    def test_seriesbook_api(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.SeriesBook.as_view()
        request = self.factory.get("")
        request.user = self.user

        with patch("bookwyrm.views.books.series.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, self.seriesbook.id)
            self.assertIsInstance(result, ActivitypubResponse)
            self.assertEqual(result.status_code, 200)
