""" tests the base functionality for activitypub dataclasses """
from io import BytesIO
import json
import pathlib
from unittest.mock import patch

from dataclasses import dataclass
from django.test import TestCase
from PIL import Image
import responses

from bookwyrm import activitypub
from bookwyrm.activitypub.base_activity import (
    ActivityObject,
    resolve_remote_id,
    set_related_field,
)
from bookwyrm.activitypub import ActivitySerializerError
from bookwyrm import models


@patch("bookwyrm.activitystreams.ActivityStream.add_status")
class BaseActivity(TestCase):
    """the super class for model-linked activitypub dataclasses"""

    def setUp(self):
        """we're probably going to re-use this so why copy/paste"""
        self.user = models.User.objects.create_user(
            "mouse", "mouse@mouse.mouse", "mouseword", local=True, localname="mouse"
        )
        self.user.remote_id = "http://example.com/a/b"
        self.user.save(broadcast=False)

        datafile = pathlib.Path(__file__).parent.joinpath("../data/ap_user.json")
        self.userdata = json.loads(datafile.read_bytes())
        # don't try to load the user icon
        del self.userdata["icon"]

        image_file = pathlib.Path(__file__).parent.joinpath(
            "../../static/images/default_avi.jpg"
        )
        image = Image.open(image_file)
        output = BytesIO()
        image.save(output, format=image.format)
        self.image_data = output.getvalue()

    def test_init(self, _):
        """simple successfuly init"""
        instance = ActivityObject(id="a", type="b")
        self.assertTrue(hasattr(instance, "id"))
        self.assertTrue(hasattr(instance, "type"))

    def test_init_missing(self, _):
        """init with missing required params"""
        with self.assertRaises(ActivitySerializerError):
            ActivityObject()

    def test_init_extra_fields(self, _):
        """init ignoring additional fields"""
        instance = ActivityObject(id="a", type="b", fish="c")
        self.assertTrue(hasattr(instance, "id"))
        self.assertTrue(hasattr(instance, "type"))

    def test_init_default_field(self, _):
        """replace an existing required field with a default field"""

        @dataclass(init=False)
        class TestClass(ActivityObject):
            """test class with default field"""

            type: str = "TestObject"

        instance = TestClass(id="a")
        self.assertEqual(instance.id, "a")
        self.assertEqual(instance.type, "TestObject")

    def test_serialize(self, _):
        """simple function for converting dataclass to dict"""
        instance = ActivityObject(id="a", type="b")
        serialized = instance.serialize()
        self.assertIsInstance(serialized, dict)
        self.assertEqual(serialized["id"], "a")
        self.assertEqual(serialized["type"], "b")

    @responses.activate
    def test_resolve_remote_id(self, _):
        """look up or load remote data"""
        # existing item
        result = resolve_remote_id("http://example.com/a/b", model=models.User)
        self.assertEqual(result, self.user)

        # remote item
        responses.add(
            responses.GET,
            "https://example.com/user/mouse",
            json=self.userdata,
            status=200,
        )

        with patch("bookwyrm.models.user.set_remote_server.delay"):
            result = resolve_remote_id(
                "https://example.com/user/mouse", model=models.User
            )
        self.assertIsInstance(result, models.User)
        self.assertEqual(result.remote_id, "https://example.com/user/mouse")
        self.assertEqual(result.name, "MOUSE?? MOUSE!!")

    def test_to_model_invalid_model(self, _):
        """catch mismatch between activity type and model type"""
        instance = ActivityObject(id="a", type="b")
        with self.assertRaises(ActivitySerializerError):
            instance.to_model(model=models.User)

    @responses.activate
    def test_to_model_image(self, _):
        """update an image field"""
        activity = activitypub.Person(
            id=self.user.remote_id,
            name="New Name",
            preferredUsername="mouse",
            inbox="http://www.com/",
            outbox="http://www.com/",
            followers="",
            summary="",
            publicKey={"id": "hi", "owner": self.user.remote_id, "publicKeyPem": "hi"},
            endpoints={},
            icon={"type": "Document", "url": "http://www.example.com/image.jpg"},
        )

        responses.add(
            responses.GET,
            "http://www.example.com/image.jpg",
            body=self.image_data,
            status=200,
        )

        self.assertIsNone(self.user.avatar.name)
        with self.assertRaises(ValueError):
            self.user.avatar.file  # pylint: disable=pointless-statement

        # this would trigger a broadcast because it's a local user
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            activity.to_model(model=models.User, instance=self.user)
        self.assertIsNotNone(self.user.avatar.file)
        self.assertEqual(self.user.name, "New Name")
        self.assertEqual(self.user.key_pair.public_key, "hi")

    def test_to_model_many_to_many(self, _):
        """annoying that these all need special handling"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            status = models.Status.objects.create(
                content="test status",
                user=self.user,
            )
        book = models.Edition.objects.create(
            title="Test Edition", remote_id="http://book.com/book"
        )
        update_data = activitypub.Note(
            id=status.remote_id,
            content=status.content,
            attributedTo=self.user.remote_id,
            published="hi",
            to=[],
            cc=[],
            tag=[
                {"type": "Mention", "name": "gerald", "href": "http://example.com/a/b"},
                {
                    "type": "Edition",
                    "name": "gerald j. books",
                    "href": "http://book.com/book",
                },
            ],
        )
        update_data.to_model(model=models.Status, instance=status)
        self.assertEqual(status.mention_users.first(), self.user)
        self.assertEqual(status.mention_books.first(), book)

    @responses.activate
    def test_to_model_one_to_many(self, _):
        """these are reversed relationships, where the secondary object
        keys the primary object but not vice versa"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            status = models.Status.objects.create(
                content="test status",
                user=self.user,
            )
        update_data = activitypub.Note(
            id=status.remote_id,
            content=status.content,
            attributedTo=self.user.remote_id,
            published="hi",
            to=[],
            cc=[],
            attachment=[
                {
                    "url": "http://www.example.com/image.jpg",
                    "name": "alt text",
                    "type": "Document",
                }
            ],
        )

        responses.add(
            responses.GET,
            "http://www.example.com/image.jpg",
            body=self.image_data,
            status=200,
        )

        # sets the celery task call to the function call
        with patch("bookwyrm.activitypub.base_activity.set_related_field.delay"):
            with patch("bookwyrm.models.status.Status.ignore_activity") as discarder:
                discarder.return_value = False
                update_data.to_model(model=models.Status, instance=status)
        self.assertIsNone(status.attachments.first())

    @responses.activate
    def test_set_related_field(self, _):
        """celery task to add back-references to created objects"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            status = models.Status.objects.create(
                content="test status",
                user=self.user,
            )
        data = {
            "url": "http://www.example.com/image.jpg",
            "name": "alt text",
            "type": "Document",
        }
        responses.add(
            responses.GET,
            "http://www.example.com/image.jpg",
            body=self.image_data,
            status=200,
        )
        set_related_field("Image", "Status", "status", status.remote_id, data)

        self.assertIsInstance(status.attachments.first(), models.Image)
        self.assertIsNotNone(status.attachments.first().image)
