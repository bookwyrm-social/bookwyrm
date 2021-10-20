""" testing models """
import json
from unittest.mock import patch
from django.test import TestCase

from bookwyrm import models


@patch("bookwyrm.activitystreams.add_user_statuses_task.delay")
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
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
            self.local_user = models.User.objects.create_user(
                "mouse", "mouse@mouse.com", "mouseword", local=True, localname="mouse"
            )
        self.local_user.remote_id = "http://local.com/user/mouse"
        self.local_user.save(broadcast=False, update_fields=["remote_id"])

    def test_user_follows_from_request(self, _):
        """convert a follow request into a follow"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay") as mock:
            request = models.UserFollowRequest.objects.create(
                user_subject=self.local_user, user_object=self.remote_user
            )
        activity = json.loads(mock.call_args[0][1])
        self.assertEqual(activity["type"], "Follow")
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

    def test_user_follows_from_request_custom_remote_id(self, _):
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

    @patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay")
    def test_follow_request_activity(self, broadcast_mock, _):
        """accept a request and make it a relationship"""
        models.UserFollowRequest.objects.create(
            user_subject=self.local_user,
            user_object=self.remote_user,
        )
        activity = json.loads(broadcast_mock.call_args[0][1])
        self.assertEqual(activity["actor"], self.local_user.remote_id)
        self.assertEqual(activity["object"], self.remote_user.remote_id)
        self.assertEqual(activity["type"], "Follow")

    @patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay")
    def test_follow_request_accept(self, broadcast_mock, _):
        """accept a request and make it a relationship"""
        self.local_user.manually_approves_followers = True
        self.local_user.save(
            broadcast=False, update_fields=["manually_approves_followers"]
        )

        request = models.UserFollowRequest.objects.create(
            user_subject=self.remote_user,
            user_object=self.local_user,
            remote_id="https://www.hi.com/",
        )
        request.accept()

        activity = json.loads(broadcast_mock.call_args[0][1])
        self.assertEqual(activity["type"], "Accept")
        self.assertEqual(activity["actor"], self.local_user.remote_id)
        self.assertEqual(activity["object"]["id"], "https://www.hi.com/")

        self.assertFalse(models.UserFollowRequest.objects.exists())
        self.assertTrue(models.UserFollows.objects.exists())
        rel = models.UserFollows.objects.get()
        self.assertEqual(rel.user_subject, self.remote_user)
        self.assertEqual(rel.user_object, self.local_user)

    @patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay")
    def test_follow_request_reject(self, broadcast_mock, _):
        """accept a request and make it a relationship"""
        self.local_user.manually_approves_followers = True
        self.local_user.save(
            broadcast=False, update_fields=["manually_approves_followers"]
        )
        request = models.UserFollowRequest.objects.create(
            user_subject=self.remote_user,
            user_object=self.local_user,
        )
        request.reject()

        activity = json.loads(broadcast_mock.call_args[0][1])
        self.assertEqual(activity["type"], "Reject")
        self.assertEqual(activity["actor"], self.local_user.remote_id)
        self.assertEqual(activity["object"]["id"], request.remote_id)

        self.assertFalse(models.UserFollowRequest.objects.exists())
        self.assertFalse(models.UserFollows.objects.exists())
