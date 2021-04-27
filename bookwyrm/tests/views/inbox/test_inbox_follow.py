""" tests incoming activities"""
import json
from unittest.mock import patch

from django.test import TestCase

from bookwyrm import models, views


# pylint: disable=too-many-public-methods
class InboxRelationships(TestCase):
    """inbox tests"""

    def setUp(self):
        """basic user and book data"""
        self.local_user = models.User.objects.create_user(
            "mouse@example.com",
            "mouse@mouse.com",
            "mouseword",
            local=True,
            localname="mouse",
        )
        self.local_user.remote_id = "https://example.com/user/mouse"
        self.local_user.save(broadcast=False)
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            self.remote_user = models.User.objects.create_user(
                "rat",
                "rat@rat.com",
                "ratword",
                local=False,
                remote_id="https://example.com/users/rat",
                inbox="https://example.com/users/rat/inbox",
                outbox="https://example.com/users/rat/outbox",
            )

        models.SiteSettings.objects.create()

    def test_follow(self):
        """remote user wants to follow local user"""
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/users/rat/follows/123",
            "type": "Follow",
            "actor": "https://example.com/users/rat",
            "object": "https://example.com/user/mouse",
        }

        self.assertFalse(models.UserFollowRequest.objects.exists())
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay") as mock:
            views.inbox.activity_task(activity)
            self.assertEqual(mock.call_count, 1)
            response_activity = json.loads(mock.call_args[0][1])
            self.assertEqual(response_activity["type"], "Accept")

        # notification created
        notification = models.Notification.objects.get()
        self.assertEqual(notification.user, self.local_user)
        self.assertEqual(notification.notification_type, "FOLLOW")

        # the request should have been deleted
        self.assertFalse(models.UserFollowRequest.objects.exists())

        # the follow relationship should exist
        follow = models.UserFollows.objects.get(user_object=self.local_user)
        self.assertEqual(follow.user_subject, self.remote_user)

    def test_follow_duplicate(self):
        """remote user wants to follow local user twice"""
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/users/rat/follows/123",
            "type": "Follow",
            "actor": "https://example.com/users/rat",
            "object": "https://example.com/user/mouse",
        }

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            views.inbox.activity_task(activity)

        # the follow relationship should exist
        follow = models.UserFollows.objects.get(user_object=self.local_user)
        self.assertEqual(follow.user_subject, self.remote_user)

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay") as mock:
            views.inbox.activity_task(activity)
            self.assertEqual(mock.call_count, 1)
            response_activity = json.loads(mock.call_args[0][1])
            self.assertEqual(response_activity["type"], "Accept")

        # the follow relationship should STILL exist
        follow = models.UserFollows.objects.get(user_object=self.local_user)
        self.assertEqual(follow.user_subject, self.remote_user)

    def test_follow_manually_approved(self):
        """needs approval before following"""
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/users/rat/follows/123",
            "type": "Follow",
            "actor": "https://example.com/users/rat",
            "object": "https://example.com/user/mouse",
        }

        self.local_user.manually_approves_followers = True
        self.local_user.save(broadcast=False)

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            views.inbox.activity_task(activity)

        # notification created
        notification = models.Notification.objects.get()
        self.assertEqual(notification.user, self.local_user)
        self.assertEqual(notification.notification_type, "FOLLOW_REQUEST")

        # the request should exist
        request = models.UserFollowRequest.objects.get()
        self.assertEqual(request.user_subject, self.remote_user)
        self.assertEqual(request.user_object, self.local_user)

        # the follow relationship should not exist
        follow = models.UserFollows.objects.all()
        self.assertEqual(list(follow), [])

    def test_undo_follow_request(self):
        """the requester cancels a follow request"""
        self.local_user.manually_approves_followers = True
        self.local_user.save(broadcast=False)
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            request = models.UserFollowRequest.objects.create(
                user_subject=self.remote_user, user_object=self.local_user
            )
        self.assertTrue(self.local_user.follower_requests.exists())

        activity = {
            "type": "Undo",
            "id": "bleh",
            "to": ["https://www.w3.org/ns/activitystreams#Public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "actor": self.remote_user.remote_id,
            "@context": "https://www.w3.org/ns/activitystreams",
            "object": {
                "@context": "https://www.w3.org/ns/activitystreams",
                "id": request.remote_id,
                "type": "Follow",
                "actor": "https://example.com/users/rat",
                "object": "https://example.com/user/mouse",
            },
        }

        views.inbox.activity_task(activity)

        self.assertFalse(self.local_user.follower_requests.exists())

    def test_unfollow(self):
        """remove a relationship"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            rel = models.UserFollows.objects.create(
                user_subject=self.remote_user, user_object=self.local_user
            )
        activity = {
            "type": "Undo",
            "id": "bleh",
            "to": ["https://www.w3.org/ns/activitystreams#Public"],
            "cc": ["https://example.com/user/mouse/followers"],
            "actor": self.remote_user.remote_id,
            "@context": "https://www.w3.org/ns/activitystreams",
            "object": {
                "id": rel.remote_id,
                "type": "Follow",
                "actor": "https://example.com/users/rat",
                "object": "https://example.com/user/mouse",
            },
        }
        self.assertEqual(self.remote_user, self.local_user.followers.first())

        views.inbox.activity_task(activity)
        self.assertIsNone(self.local_user.followers.first())

    def test_follow_accept(self):
        """a remote user approved a follow request from local"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            rel = models.UserFollowRequest.objects.create(
                user_subject=self.local_user, user_object=self.remote_user
            )
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/users/rat/follows/123#accepts",
            "type": "Accept",
            "actor": "https://example.com/users/rat",
            "object": {
                "id": rel.remote_id,
                "type": "Follow",
                "actor": "https://example.com/user/mouse",
                "object": "https://example.com/users/rat",
            },
        }

        self.assertEqual(models.UserFollowRequest.objects.count(), 1)

        views.inbox.activity_task(activity)

        # request should be deleted
        self.assertEqual(models.UserFollowRequest.objects.count(), 0)

        # relationship should be created
        follows = self.remote_user.followers
        self.assertEqual(follows.count(), 1)
        self.assertEqual(follows.first(), self.local_user)

    def test_follow_reject(self):
        """turn down a follow request"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            rel = models.UserFollowRequest.objects.create(
                user_subject=self.local_user, user_object=self.remote_user
            )
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/users/rat/follows/123#accepts",
            "type": "Reject",
            "actor": "https://example.com/users/rat",
            "object": {
                "id": rel.remote_id,
                "type": "Follow",
                "actor": "https://example.com/user/mouse",
                "object": "https://example.com/users/rat",
            },
        }

        self.assertEqual(models.UserFollowRequest.objects.count(), 1)

        views.inbox.activity_task(activity)

        # request should be deleted
        self.assertFalse(models.UserFollowRequest.objects.exists())
        self.assertFalse(self.remote_user.followers.exists())
