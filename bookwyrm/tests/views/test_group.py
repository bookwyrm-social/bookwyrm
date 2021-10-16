""" test for app action functionality """
from unittest.mock import patch
from django.contrib.auth import decorators

from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views, forms
from bookwyrm.tests.validate_html import validate_html


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay")
class GroupViews(TestCase):
    """view group and edit details"""

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

            self.testgroup = models.Group.objects.create(
                name="Test Group",
                description="Initial description",
                user=self.local_user,
                privacy="public",
            )
            self.membership = models.GroupMember.objects.create(
                group=self.testgroup, user=self.local_user
            )

        models.SiteSettings.objects.create()

    def test_group_get(self, _):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Group.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request, group_id=self.testgroup.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_usergroups_get(self, _):
        """there are so many views, this just makes sure it LOADS"""
        view = views.UserGroups.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request, username="mouse@local.com")
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    @patch("bookwyrm.suggested_users.SuggestedUsers.get_suggestions")
    def test_findusers_get(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.FindUsers.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request, group_id=self.testgroup.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_group_create(self, _):
        """create group view"""
        view = views.UserGroups.as_view()
        request = self.factory.post(
            "",
            {
                "name": "A group",
                "description": "wowzers",
                "privacy": "unlisted",
                "user": self.local_user.id,
            },
        )
        request.user = self.local_user
        result = view(request, "username")

        self.assertEqual(result.status_code, 302)
        new_group = models.Group.objects.filter(name="A group").get()
        self.assertEqual(new_group.description, "wowzers")
        self.assertEqual(new_group.privacy, "unlisted")
        self.assertTrue(
            models.GroupMember.objects.filter(
                group=new_group, user=self.local_user
            ).exists()
        )

    def test_group_edit(self, _):
        """test editing a "group" database entry"""

        view = views.Group.as_view()
        request = self.factory.post(
            "",
            {
                "name": "Updated Group name",
                "description": "wow",
                "privacy": "direct",
                "user": self.local_user.id,
            },
        )
        request.user = self.local_user

        result = view(request, group_id=self.testgroup.id)
        self.assertEqual(result.status_code, 302)
        self.testgroup.refresh_from_db()
        self.assertEqual(self.testgroup.name, "Updated Group name")
        self.assertEqual(self.testgroup.description, "wow")
        self.assertEqual(self.testgroup.privacy, "direct")
