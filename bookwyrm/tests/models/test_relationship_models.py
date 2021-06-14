""" testing models """
from unittest.mock import patch
from django.test import TestCase

from bookwyrm import models


class Relationship(TestCase):
    """following, blocking, stuff like that"""

    def setUp(self):
        """we need some users for this"""
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
        self.local_user = models.User.objects.create_user(
            "mouse", "mouse@mouse.com", "mouseword", local=True, localname="mouse"
        )
        self.local_user.remote_id = "http://local.com/user/mouse"
        self.local_user.save(broadcast=False)

    def test_user_follows_from_request(self):
        """convert a follow request into a follow"""
        real_broadcast = models.UserFollowRequest.broadcast

        def mock_broadcast(_, activity, user):
            """introspect what's being sent out"""
            self.assertEqual(user.remote_id, self.local_user.remote_id)
            self.assertEqual(activity["type"], "Follow")

        models.UserFollowRequest.broadcast = mock_broadcast
        request = models.UserFollowRequest.objects.create(
            user_subject=self.local_user, user_object=self.remote_user
        )
        self.assertEqual(
            request.remote_id, "http://local.com/user/mouse#follows/%d" % request.id
        )
        self.assertEqual(request.status, "follow_request")

        rel = models.UserFollows.from_request(request)
        self.assertEqual(
            rel.remote_id, "http://local.com/user/mouse#follows/%d" % request.id
        )
        self.assertEqual(rel.status, "follows")
        self.assertEqual(rel.user_subject, self.local_user)
        self.assertEqual(rel.user_object, self.remote_user)
        models.UserFollowRequest.broadcast = real_broadcast

    def test_user_follows_from_request_custom_remote_id(self):
        """store a specific remote id for a relationship provided by remote"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            request = models.UserFollowRequest.objects.create(
                user_subject=self.local_user,
                user_object=self.remote_user,
                remote_id="http://antoher.server/sdkfhskdjf/23",
            )
        self.assertEqual(request.remote_id, "http://antoher.server/sdkfhskdjf/23")
        self.assertEqual(request.status, "follow_request")

        rel = models.UserFollows.from_request(request)
        self.assertEqual(rel.remote_id, "http://antoher.server/sdkfhskdjf/23")
        self.assertEqual(rel.status, "follows")
        self.assertEqual(rel.user_subject, self.local_user)
        self.assertEqual(rel.user_object, self.remote_user)

    def test_follow_request_activity(self):
        """accept a request and make it a relationship"""
        real_broadcast = models.UserFollowRequest.broadcast

        def mock_broadcast(_, activity, user):
            self.assertEqual(user.remote_id, self.local_user.remote_id)
            self.assertEqual(activity["actor"], self.local_user.remote_id)
            self.assertEqual(activity["object"], self.remote_user.remote_id)
            self.assertEqual(activity["type"], "Follow")

        models.UserFollowRequest.broadcast = mock_broadcast
        models.UserFollowRequest.objects.create(
            user_subject=self.local_user,
            user_object=self.remote_user,
        )
        models.UserFollowRequest.broadcast = real_broadcast

    def test_follow_request_accept(self):
        """accept a request and make it a relationship"""
        real_broadcast = models.UserFollowRequest.broadcast

        def mock_broadcast(_, activity, user):
            self.assertEqual(user.remote_id, self.local_user.remote_id)
            self.assertEqual(activity["type"], "Accept")
            self.assertEqual(activity["actor"], self.local_user.remote_id)
            self.assertEqual(activity["object"]["id"], "https://www.hi.com/")

        self.local_user.manually_approves_followers = True
        self.local_user.save(broadcast=False)
        models.UserFollowRequest.broadcast = mock_broadcast
        request = models.UserFollowRequest.objects.create(
            user_subject=self.remote_user,
            user_object=self.local_user,
            remote_id="https://www.hi.com/",
        )
        request.accept()

        self.assertFalse(models.UserFollowRequest.objects.exists())
        self.assertTrue(models.UserFollows.objects.exists())
        rel = models.UserFollows.objects.get()
        self.assertEqual(rel.user_subject, self.remote_user)
        self.assertEqual(rel.user_object, self.local_user)
        models.UserFollowRequest.broadcast = real_broadcast

    def test_follow_request_reject(self):
        """accept a request and make it a relationship"""
        real_broadcast = models.UserFollowRequest.broadcast

        def mock_reject(_, activity, user):
            self.assertEqual(user.remote_id, self.local_user.remote_id)
            self.assertEqual(activity["type"], "Reject")
            self.assertEqual(activity["actor"], self.local_user.remote_id)
            self.assertEqual(activity["object"]["id"], request.remote_id)

        models.UserFollowRequest.broadcast = mock_reject
        self.local_user.manually_approves_followers = True
        self.local_user.save(broadcast=False)
        request = models.UserFollowRequest.objects.create(
            user_subject=self.remote_user,
            user_object=self.local_user,
        )
        request.reject()

        self.assertFalse(models.UserFollowRequest.objects.exists())
        self.assertFalse(models.UserFollows.objects.exists())
        models.UserFollowRequest.broadcast = real_broadcast
