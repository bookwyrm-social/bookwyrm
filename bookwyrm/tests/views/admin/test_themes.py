""" test for app action functionality """
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views
from bookwyrm.management.commands import initdb
from bookwyrm.tests.validate_html import validate_html


class AdminThemesViews(TestCase):
    """Edit site settings"""

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
                "mouse@mouse.mouse",
                "password",
                local=True,
                localname="mouse",
            )
            cls.another_user = models.User.objects.create_user(
                "rat@local.com",
                "rat@rat.rat",
                "password",
                local=True,
                localname="rat",
            )
        initdb.init_groups()
        initdb.init_permissions()
        group = Group.objects.get(name="admin")
        cls.local_user.groups.set([group])

        cls.site = models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    def test_themes_get(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Themes.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_themes_post(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Themes.as_view()

        form = forms.ThemeForm()
        form.data["name"] = "test theme"
        form.data["path"] = "not/a/path.scss"
        request = self.factory.post("", form.data)
        request.user = self.local_user

        result = view(request)

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        theme = models.Theme.objects.last()
        self.assertEqual(theme.name, "test theme")
        self.assertEqual(theme.path, "not/a/path.scss")

    def test_themes_post_forbidden(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Themes.as_view()

        form = forms.ThemeForm()
        form.data["name"] = "test theme"
        form.data["path"] = "not/a/path.scss"
        request = self.factory.post("", form.data)
        request.user = self.another_user

        with self.assertRaises(PermissionDenied):
            view(request)

    def test_test_theme(self):
        """Testing testing testing test"""
        theme = models.Theme.objects.first()
        self.assertIsNone(theme.loads)
        request = self.factory.post("")
        request.user = self.local_user

        views.test_theme(request, theme.id)
        theme.refresh_from_db()
        self.assertTrue(theme.loads)

    def test_test_theme_broken(self):
        """Testing test for testing when it's a bad theme"""
        theme = models.Theme.objects.create(name="bad theme", path="dsf/sdf/sdf.sdf")
        self.assertIsNone(theme.loads)
        request = self.factory.post("")
        request.user = self.local_user

        views.test_theme(request, theme.id)
        theme.refresh_from_db()
        self.assertIs(False, theme.loads)
