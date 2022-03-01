""" test for app action functionality """
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views
from bookwyrm.tests.validate_html import validate_html


class SetupViews(TestCase):
    """activity feed, statuses, dms"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        self.site = models.SiteSettings.objects.create(install_mode=True)

    def test_instance_config_permission_denied(self):
        """there are so many views, this just makes sure it LOADS"""
        self.site.install_mode = False
        self.site.save()
        view = views.InstanceConfig.as_view()
        request = self.factory.get("")
        with self.assertRaises(PermissionDenied):
            view(request)

    def test_instance_config(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.InstanceConfig.as_view()
        request = self.factory.get("")

        result = view(request)

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_create_admin_get(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.CreateAdmin.as_view()
        request = self.factory.get("")

        result = view(request)

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_create_admin_post(self):
        """there are so many views, this just makes sure it LOADS"""
        self.site.name = "hello"
        self.site.save()
        self.assertFalse(self.site.allow_registration)
        self.assertTrue(self.site.require_confirm_email)
        self.assertTrue(self.site.install_mode)

        view = views.CreateAdmin.as_view()

        form = forms.RegisterForm()
        form.data["localname"] = "mouse"
        form.data["password"] = "mouseword"
        form.data["email"] = "aaa@bbb.ccc"
        request = self.factory.post("", form.data)

        with patch("bookwyrm.views.setup.login") as mock:
            view(request)
        self.assertTrue(mock.called)

        self.site.refresh_from_db()
        self.assertFalse(self.site.install_mode)

        user = models.User.objects.get()
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.shelf_set.exists())
