""" test for app action functionality """
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.tests.validate_html import validate_html


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
class GroupViews(TestCase):
    """view group and edit details"""

    def setUp(self):  # pylint: disable=invalid-name
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
            self.rat = models.User.objects.create_user(
                "rat@local.com",
                "rat@rat.rat",
                "password",
                local=True,
                localname="rat",
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
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False

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

    def test_group_get_anonymous(self, _):
        """there are so many views, this just makes sure it LOADS"""
        self.testgroup.privacy = "followers"
        self.testgroup.save()

        view = views.Group.as_view()
        request = self.factory.get("")
        request.user = self.anonymous_user
        with self.assertRaises(Http404):
            view(request, group_id=self.testgroup.id)

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

    def test_findusers_get_with_query(self, _):
        """there are so many views, this just makes sure it LOADS"""
        view = views.FindUsers.as_view()
        request = self.factory.get("", {"user_query": "rat"})
        request.user = self.local_user
        with patch("bookwyrm.suggested_users.SuggestedUsers.get_suggestions") as mock:
            mock.return_value = models.User.objects.all()
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

    def test_group_create_permission_denied(self, _):
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
        request.user = self.rat

        with self.assertRaises(PermissionDenied):
            view(request, "username")

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

    def test_delete_group(self, _):
        """delete a group"""
        request = self.factory.post("")
        request.user = self.local_user
        views.delete_group(request, self.testgroup.id)
        self.assertFalse(models.Group.objects.exists())

    def test_invite_member(self, _):
        """invite a member to a group"""
        request = self.factory.post(
            "",
            {
                "group": self.testgroup.id,
                "user": self.rat.localname,
            },
        )
        request.user = self.local_user
        result = views.invite_member(request)
        self.assertEqual(result.status_code, 302)

        invite = models.GroupMemberInvitation.objects.get()
        self.assertEqual(invite.user, self.rat)
        self.assertEqual(invite.group, self.testgroup)

    def test_invite_member_twice(self, _):
        """invite a member to a group again"""
        request = self.factory.post(
            "",
            {
                "group": self.testgroup.id,
                "user": self.rat.localname,
            },
        )
        request.user = self.local_user
        result = views.invite_member(request)
        self.assertEqual(result.status_code, 302)
        result = views.invite_member(request)
        self.assertEqual(result.status_code, 302)

    def test_remove_member_denied(self, _):
        """remove member"""
        request = self.factory.post(
            "",
            {
                "group": self.testgroup.id,
                "user": self.local_user.localname,
            },
        )
        request.user = self.local_user
        result = views.remove_member(request)
        self.assertEqual(result.status_code, 400)

    def test_remove_member_non_member(self, _):
        """remove member but wait, that's not a member"""
        request = self.factory.post(
            "",
            {
                "group": self.testgroup.id,
                "user": self.rat.localname,
            },
        )
        request.user = self.local_user
        result = views.remove_member(request)
        # nothing happens
        self.assertEqual(result.status_code, 302)

    def test_remove_member_invited(self, _):
        """remove an invited member"""
        models.GroupMemberInvitation.objects.create(
            user=self.rat,
            group=self.testgroup,
        )
        request = self.factory.post(
            "",
            {
                "group": self.testgroup.id,
                "user": self.rat.localname,
            },
        )
        request.user = self.local_user
        result = views.remove_member(request)
        self.assertEqual(result.status_code, 302)
        self.assertFalse(models.GroupMemberInvitation.objects.exists())

    def test_remove_member_existing_member(self, _):
        """remove an invited member"""
        models.GroupMember.objects.create(
            user=self.rat,
            group=self.testgroup,
        )
        request = self.factory.post(
            "",
            {
                "group": self.testgroup.id,
                "user": self.rat.localname,
            },
        )
        request.user = self.local_user
        result = views.remove_member(request)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(models.GroupMember.objects.count(), 1)
        self.assertEqual(models.GroupMember.objects.first().user, self.local_user)
        notification = models.Notification.objects.get()
        self.assertEqual(notification.user, self.rat)
        self.assertEqual(notification.related_group, self.testgroup)
        self.assertEqual(notification.notification_type, "REMOVE")

    def test_remove_member_remove_self(self, _):
        """Leave a group"""
        models.GroupMember.objects.create(
            user=self.rat,
            group=self.testgroup,
        )
        request = self.factory.post(
            "",
            {
                "group": self.testgroup.id,
                "user": self.rat.localname,
            },
        )
        request.user = self.rat
        result = views.remove_member(request)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(models.GroupMember.objects.count(), 1)
        self.assertEqual(models.GroupMember.objects.first().user, self.local_user)
        notification = models.Notification.objects.get()
        self.assertEqual(notification.user, self.local_user)
        self.assertEqual(notification.related_group, self.testgroup)
        self.assertEqual(notification.notification_type, "LEAVE")

    def test_accept_membership(self, _):
        """accept an invite"""
        models.GroupMemberInvitation.objects.create(
            user=self.rat,
            group=self.testgroup,
        )
        request = self.factory.post("", {"group": self.testgroup.id})
        request.user = self.rat
        views.accept_membership(request)

        self.assertFalse(models.GroupMemberInvitation.objects.exists())
        self.assertTrue(self.rat in [m.user for m in self.testgroup.memberships.all()])

    def test_reject_membership(self, _):
        """reject an invite"""
        models.GroupMemberInvitation.objects.create(
            user=self.rat,
            group=self.testgroup,
        )
        request = self.factory.post("", {"group": self.testgroup.id})
        request.user = self.rat
        views.reject_membership(request)

        self.testgroup.refresh_from_db()
        self.assertFalse(models.GroupMemberInvitation.objects.exists())
        self.assertFalse(self.rat in [m.user for m in self.testgroup.memberships.all()])
