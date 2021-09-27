""" testing models """
from unittest.mock import patch
from django.http import Http404
from django.test import TestCase

from bookwyrm import models
from bookwyrm.models import base_model
from bookwyrm.settings import DOMAIN


# pylint: disable=attribute-defined-outside-init
class BaseModel(TestCase):
    """functionality shared across models"""

    def setUp(self):
        """shared data"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
            self.local_user = models.User.objects.create_user(
                "mouse", "mouse@mouse.com", "mouseword", local=True, localname="mouse"
            )
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

        class BookWyrmTestModel(base_model.BookWyrmModel):
            """just making it not abstract"""

        self.test_model = BookWyrmTestModel()

    def test_remote_id(self):
        """these should be generated"""
        self.test_model.id = 1
        expected = self.test_model.get_remote_id()
        self.assertEqual(expected, f"https://{DOMAIN}/bookwyrmtestmodel/1")

    def test_remote_id_with_user(self):
        """format of remote id when there's a user object"""
        self.test_model.user = self.local_user
        self.test_model.id = 1
        expected = self.test_model.get_remote_id()
        self.assertEqual(expected, f"https://{DOMAIN}/user/mouse/bookwyrmtestmodel/1")

    def test_set_remote_id(self):
        """this function sets remote ids after creation"""
        # using Work because it BookWrymModel is abstract and this requires save
        # Work is a relatively not-fancy model.
        instance = models.Work.objects.create(title="work title")
        instance.remote_id = None
        base_model.set_remote_id(None, instance, True)
        self.assertEqual(instance.remote_id, f"https://{DOMAIN}/book/{instance.id}")

        # shouldn't set remote_id if it's not created
        instance.remote_id = None
        base_model.set_remote_id(None, instance, False)
        self.assertIsNone(instance.remote_id)

    @patch("bookwyrm.activitystreams.add_status_task.delay")
    def test_object_visible_to_user(self, _):
        """does a user have permission to view an object"""
        obj = models.Status.objects.create(
            content="hi", user=self.remote_user, privacy="public"
        )
        self.assertIsNone(obj.raise_visible_to_user(self.local_user))

        obj = models.Shelf.objects.create(
            name="test", user=self.remote_user, privacy="unlisted"
        )
        self.assertIsNone(obj.raise_visible_to_user(self.local_user))

        obj = models.Status.objects.create(
            content="hi", user=self.remote_user, privacy="followers"
        )
        with self.assertRaises(Http404):
            obj.raise_visible_to_user(self.local_user)

        obj = models.Status.objects.create(
            content="hi", user=self.remote_user, privacy="direct"
        )
        with self.assertRaises(Http404):
            obj.raise_visible_to_user(self.local_user)

        obj = models.Status.objects.create(
            content="hi", user=self.remote_user, privacy="direct"
        )
        obj.mention_users.add(self.local_user)
        self.assertIsNone(obj.raise_visible_to_user(self.local_user))

    @patch("bookwyrm.activitystreams.add_status_task.delay")
    def test_object_visible_to_user_follower(self, _):
        """what you can see if you follow a user"""
        self.remote_user.followers.add(self.local_user)
        obj = models.Status.objects.create(
            content="hi", user=self.remote_user, privacy="followers"
        )
        self.assertIsNone(obj.raise_visible_to_user(self.local_user))

        obj = models.Status.objects.create(
            content="hi", user=self.remote_user, privacy="direct"
        )
        with self.assertRaises(Http404):
            obj.raise_visible_to_user(self.local_user)

        obj = models.Status.objects.create(
            content="hi", user=self.remote_user, privacy="direct"
        )
        obj.mention_users.add(self.local_user)
        self.assertIsNone(obj.raise_visible_to_user(self.local_user))

    @patch("bookwyrm.activitystreams.add_status_task.delay")
    def test_object_visible_to_user_blocked(self, _):
        """you can't see it if they block you"""
        self.remote_user.blocks.add(self.local_user)
        obj = models.Status.objects.create(
            content="hi", user=self.remote_user, privacy="public"
        )
        with self.assertRaises(Http404):
            obj.raise_visible_to_user(self.local_user)

        obj = models.Shelf.objects.create(
            name="test", user=self.remote_user, privacy="unlisted"
        )
        with self.assertRaises(Http404):
            obj.raise_visible_to_user(self.local_user)
