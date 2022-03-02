""" test for context processor """
from unittest.mock import patch
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models
from bookwyrm.context_processors import site_settings


class ContextProcessor(TestCase):
    """pages you land on without really trying"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.mouse",
                "password",
                local=True,
                localname="mouse",
            )
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False
        self.site = models.SiteSettings.objects.create()

    def test_theme_unset(self):
        """logged in user, no selected theme"""
        request = self.factory.get("")
        request.user = self.local_user
        settings = site_settings(request)
        self.assertEqual(settings["site_theme"], "css/themes/bookwyrm-light.scss")

    def test_theme_unset_logged_out(self):
        """logged out user, no selected theme"""
        request = self.factory.get("")
        request.user = self.anonymous_user
        settings = site_settings(request)
        self.assertEqual(settings["site_theme"], "css/themes/bookwyrm-light.scss")

    def test_theme_instance_default(self):
        """logged in user, instance default theme"""
        self.site.default_theme = models.Theme.objects.get(name="BookWyrm Dark")
        self.site.save()

        request = self.factory.get("")
        request.user = self.local_user
        settings = site_settings(request)
        self.assertEqual(settings["site_theme"], "css/themes/bookwyrm-dark.scss")

    def test_theme_instance_default_logged_out(self):
        """logged out user, instance default theme"""
        self.site.default_theme = models.Theme.objects.get(name="BookWyrm Dark")
        self.site.save()

        request = self.factory.get("")
        request.user = self.anonymous_user
        settings = site_settings(request)
        self.assertEqual(settings["site_theme"], "css/themes/bookwyrm-dark.scss")

    def test_theme_user_set(self):
        """logged in user, user theme"""
        self.local_user.theme = models.Theme.objects.get(name="BookWyrm Dark")
        self.local_user.save(broadcast=False, update_fields=["theme"])

        request = self.factory.get("")
        request.user = self.local_user
        settings = site_settings(request)
        self.assertEqual(settings["site_theme"], "css/themes/bookwyrm-dark.scss")

    def test_theme_user_set_instance_default(self):
        """logged in user, instance default theme"""
        self.site.default_theme = models.Theme.objects.get(name="BookWyrm Dark")
        self.site.save()

        self.local_user.theme = models.Theme.objects.get(name="BookWyrm Light")
        self.local_user.save(broadcast=False, update_fields=["theme"])

        request = self.factory.get("")
        request.user = self.local_user
        settings = site_settings(request)
        self.assertEqual(settings["site_theme"], "css/themes/bookwyrm-light.scss")
