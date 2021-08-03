""" test for app action functionality """
import json
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views


class BookViews(TestCase):
    """books books books"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.com",
            "mouseword",
            local=True,
            localname="mouse",
            remote_id="https://example.com/users/mouse",
        )
        with patch("bookwyrm.models.user.set_remote_server"):
            self.remote_user = models.User.objects.create_user(
                "rat",
                "rat@email.com",
                "ratword",
                local=False,
                remote_id="https://example.com/users/rat",
                inbox="https://example.com/users/rat/inbox",
                outbox="https://example.com/users/rat/outbox",
            )
        self.group = Group.objects.create(name="editor")
        self.group.permissions.add(
            Permission.objects.create(
                name="edit_book",
                codename="edit_book",
                content_type=ContentType.objects.get_for_model(models.User),
            ).id
        )
        self.work = models.Work.objects.create(title="Test Work")
        self.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=self.work,
        )

    def test_handle_follow_remote(self):
        """send a follow request"""
        request = self.factory.post("", {"user": self.remote_user.username})
        request.user = self.local_user
        self.assertEqual(models.UserFollowRequest.objects.count(), 0)

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            views.follow(request)

        rel = models.UserFollowRequest.objects.get()

        self.assertEqual(rel.user_subject, self.local_user)
        self.assertEqual(rel.user_object, self.remote_user)
        self.assertEqual(rel.status, "follow_request")

    def test_handle_follow_local_manually_approves(self):
        """send a follow request"""
        rat = models.User.objects.create_user(
            "rat@local.com",
            "rat@rat.com",
            "ratword",
            local=True,
            localname="rat",
            remote_id="https://example.com/users/rat",
            manually_approves_followers=True,
        )
        request = self.factory.post("", {"user": rat})
        request.user = self.local_user
        self.assertEqual(models.UserFollowRequest.objects.count(), 0)

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            views.follow(request)
        rel = models.UserFollowRequest.objects.get()

        self.assertEqual(rel.user_subject, self.local_user)
        self.assertEqual(rel.user_object, rat)
        self.assertEqual(rel.status, "follow_request")

    def test_handle_follow_local(self):
        """send a follow request"""
        rat = models.User.objects.create_user(
            "rat@local.com",
            "rat@rat.com",
            "ratword",
            local=True,
            localname="rat",
            remote_id="https://example.com/users/rat",
        )
        request = self.factory.post("", {"user": rat})
        request.user = self.local_user
        self.assertEqual(models.UserFollowRequest.objects.count(), 0)

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            views.follow(request)

        rel = models.UserFollows.objects.get()

        self.assertEqual(rel.user_subject, self.local_user)
        self.assertEqual(rel.user_object, rat)
        self.assertEqual(rel.status, "follows")

    def test_handle_unfollow(self):
        """send an unfollow"""
        request = self.factory.post("", {"user": self.remote_user.username})
        request.user = self.local_user
        self.remote_user.followers.add(self.local_user)
        self.assertEqual(self.remote_user.followers.count(), 1)
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay") as mock:
            views.unfollow(request)
            self.assertEqual(mock.call_count, 1)
            activity = json.loads(mock.call_args_list[0][0][1])
            self.assertEqual(activity["type"], "Undo")

        self.assertEqual(self.remote_user.followers.count(), 0)

    def test_handle_accept(self):
        """accept a follow request"""
        self.local_user.manually_approves_followers = True
        self.local_user.save(broadcast=False)
        request = self.factory.post("", {"user": self.remote_user.username})
        request.user = self.local_user
        rel = models.UserFollowRequest.objects.create(
            user_subject=self.remote_user, user_object=self.local_user
        )

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            views.accept_follow_request(request)
        # request should be deleted
        self.assertEqual(models.UserFollowRequest.objects.filter(id=rel.id).count(), 0)
        # follow relationship should exist
        self.assertEqual(self.local_user.followers.first(), self.remote_user)

    def test_handle_reject(self):
        """reject a follow request"""
        self.local_user.manually_approves_followers = True
        self.local_user.save(broadcast=False)
        request = self.factory.post("", {"user": self.remote_user.username})
        request.user = self.local_user
        rel = models.UserFollowRequest.objects.create(
            user_subject=self.remote_user, user_object=self.local_user
        )

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            views.delete_follow_request(request)
        # request should be deleted
        self.assertEqual(models.UserFollowRequest.objects.filter(id=rel.id).count(), 0)
        # follow relationship should not exist
        self.assertEqual(models.UserFollows.objects.filter(id=rel.id).count(), 0)
