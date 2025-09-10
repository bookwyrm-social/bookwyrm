""" test ActivityPub Add and Remove activities with None target field """
import json
from unittest.mock import patch
from django.test import TestCase

from bookwyrm import models
from bookwyrm.activitypub import ActivitySerializerError, Add, Remove


class AddRemoveActivitiesTest(TestCase):
    """test Add and Remove ActivityPub activities"""

    @classmethod
    def setUpTestData(cls):
        """we need basic test data and mocks"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.com",
                "mouseword",
                local=True,
                localname="mouse",
                remote_id="https://example.com/users/mouse",
            )
        work = models.Work.objects.create(title="Test Work")
        cls.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=work,
        )
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            cls.shelf = models.Shelf.objects.create(name="Test Shelf", user=cls.local_user)
            cls.shelf_book = models.ShelfBook.objects.create(
                book=cls.book,
                user=cls.local_user,
                shelf=cls.shelf,
            )

        models.SiteSettings.objects.create()

    def test_add_activity_with_none_target_fails(self):
        """Add activity should fail serialization when target is None"""
        # Create an Add activity with None target - should fail
        with self.assertRaises(ActivitySerializerError):
            add_activity = Add(
                actor=self.local_user.remote_id,
                object=self.shelf_book,
                target=None  # This should cause serialization to fail
            )
            # Try to serialize to JSON - should raise ActivitySerializerError
            json.dumps(add_activity.to_activity())

    def test_remove_activity_with_none_target_fails(self):
        """Remove activity should fail serialization when target is None"""
        # Create a Remove activity with None target - should fail
        with self.assertRaises(ActivitySerializerError):
            remove_activity = Remove(
                actor=self.local_user.remote_id,
                object=self.shelf_book,
                target=None  # This should cause serialization to fail
            )
            # Try to serialize to JSON - should raise ActivitySerializerError
            json.dumps(remove_activity.to_activity())

    def test_add_activity_with_valid_target_succeeds(self):
        """Add activity should succeed when target is provided"""
        # Create an Add activity with valid target - should succeed
        add_activity = Add(
            id="https://example.com/activities/1",
            actor=self.local_user.remote_id,
            object=self.shelf_book,
            target=self.shelf.remote_id
        )
        # Should not raise an exception
        activity_dict = add_activity.to_activity()
        self.assertEqual(activity_dict["type"], "Add")
        self.assertEqual(activity_dict["target"], self.shelf.remote_id)

    def test_remove_activity_with_valid_target_succeeds(self):
        """Remove activity should succeed when target is provided"""
        # Create a Remove activity with valid target - should succeed
        remove_activity = Remove(
            id="https://example.com/activities/2",
            actor=self.local_user.remote_id,
            object=self.shelf_book,
            target=self.shelf.remote_id
        )
        # Should not raise an exception
        activity_dict = remove_activity.to_activity()
        self.assertEqual(activity_dict["type"], "Remove")
        self.assertEqual(activity_dict["target"], self.shelf.remote_id)