""" test for app action functionality """
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views
from bookwyrm.management.commands import initdb
from bookwyrm.tests.validate_html import validate_html


class SiteSettingsViews(TestCase):
    """Edit site settings"""

    # pylint: disable=invalid-name
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
        initdb.init_groups()
        initdb.init_permissions()
        group = Group.objects.get(name="admin")
        self.local_user.groups.set([group])

        self.site = models.SiteSettings.objects.create()

    def test_site_get(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Site.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_site_post(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Site.as_view()
        form = forms.SiteForm()
        form.data["name"] = "Name!"
        form.data["instance_tagline"] = "hi"
        form.data["instance_description"] = "blah"
        form.data["registration_closed_text"] = "blah"
        form.data["invite_request_text"] = "blah"
        form.data["code_of_conduct"] = "blah"
        form.data["privacy_policy"] = "blah"
        form.data["show_impressum"] = False
        form.data["impressum"] = "bleh"
        request = self.factory.post("", form.data)
        request.user = self.local_user

        result = view(request)

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        site = models.SiteSettings.objects.get()
        self.assertEqual(site.name, "Name!")

    def test_site_post_invalid(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Site.as_view()
        form = forms.SiteForm()
        request = self.factory.post("", form.data)
        request.user = self.local_user

        result = view(request)

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        self.site.refresh_from_db()
        self.assertEqual(self.site.name, "BookWyrm")
