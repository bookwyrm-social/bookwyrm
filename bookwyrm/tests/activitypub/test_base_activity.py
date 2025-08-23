""" tests the base functionality for activitypub dataclasses """
import json
import pathlib
from unittest.mock import patch

from dataclasses import dataclass
from django.test import TestCase
from requests.exceptions import HTTPError
import responses


from bookwyrm import activitypub
from bookwyrm.activitypub.base_activity import (
    ActivityObject,
    resolve_remote_id,
    set_related_field,
    get_representative,
    get_activitypub_data,
)
from bookwyrm.activitypub import ActivitySerializerError
from bookwyrm import models


@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.suggested_users.rerank_user_task.delay")
@patch("bookwyrm.suggested_users.remove_user_task.delay")
@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
class BaseActivity(TestCase):
    """the super class for model-linked activitypub dataclasses"""

    @classmethod
    def setUpTestData(cls):
        """we're probably going to re-use this so why copy/paste"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "mouseword", local=True, localname="mouse"
            )
        cls.user.remote_id = "http://example.com/a/b"
        cls.user.save(broadcast=False, update_fields=["remote_id"])

    def setUp(self):
        datafile = pathlib.Path(__file__).parent.joinpath("../data/ap_user.json")
        self.userdata = json.loads(datafile.read_bytes())
        # don't try to load the user icon
        del self.userdata["icon"]

        remote_datafile = pathlib.Path(__file__).parent.joinpath(
            "../data/ap_user_external.json"
        )
        self.remote_userdata = json.loads(remote_datafile.read_bytes())
        del self.remote_userdata["icon"]

        alias_datafile = pathlib.Path(__file__).parent.joinpath(
            "../data/ap_user_aliased.json"
        )
        self.alias_userdata = json.loads(alias_datafile.read_bytes())
        del self.alias_userdata["icon"]

        image_path = pathlib.Path(__file__).parent.joinpath(
            "../../static/images/default_avi.jpg"
        )
        with open(image_path, "rb") as image_file:
            self.image_data = image_file.read()

    def test_get_representative_not_existing(self, *_):
        """test that an instance representative actor is created if it does not exist"""
        representative = get_representative()
        self.assertIsInstance(representative, models.User)

    def test_init(self, *_):
        """simple successfully init"""
        instance = ActivityObject(id="a", type="b")
        self.assertTrue(hasattr(instance, "id"))
        self.assertTrue(hasattr(instance, "type"))

    def test_init_missing(self, *_):
        """init with missing required params"""
        with self.assertRaises(ActivitySerializerError):
            ActivityObject()

    def test_init_extra_fields(self, *_):
        """init ignoring additional fields"""
        instance = ActivityObject(id="a", type="b", fish="c")
        self.assertTrue(hasattr(instance, "id"))
        self.assertTrue(hasattr(instance, "type"))

    def test_init_default_field(self, *_):
        """replace an existing required field with a default field"""

        @dataclass(init=False)
        class TestClass(ActivityObject):
            """test class with default field"""

            type: str = "TestObject"

        instance = TestClass(id="a")
        self.assertEqual(instance.id, "a")
        self.assertEqual(instance.type, "TestObject")

    def test_serialize(self, *_):
        """simple function for converting dataclass to dict"""
        instance = ActivityObject(id="a", type="b")
        serialized = instance.serialize()
        self.assertIsInstance(serialized, dict)
        self.assertEqual(serialized["id"], "a")
        self.assertEqual(serialized["type"], "b")

    @responses.activate
    def test_resolve_remote_id(self, *_):
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

    @responses.activate
    def test_resolve_remote_alias(self, *_):
        """look up or load user who has an unknown alias"""

        self.assertEqual(models.User.objects.count(), 1)

        # remote user with unknown user as an alias
        responses.add(
            responses.GET,
            "https://example.com/user/moose",
            json=self.alias_userdata,
            status=200,
        )

        responses.add(
            responses.GET,
            "https://example.com/user/ali",
            json=self.remote_userdata,
            status=200,
        )

        with patch("bookwyrm.models.user.set_remote_server.delay"):
            result = resolve_remote_id(
                "https://example.com/user/moose", model=models.User
            )

        self.assertTrue(
            models.User.objects.filter(
                remote_id="https://example.com/user/moose"
            ).exists()
        )  # moose has been added to DB
        self.assertTrue(
            models.User.objects.filter(
                remote_id="https://example.com/user/ali"
            ).exists()
        )  # Ali has been added to DB
        self.assertIsInstance(result, models.User)
        self.assertEqual(result.name, "moose?? moose!!")
        alias = models.User.objects.last()
        self.assertEqual(alias.name, "Ali As")
        self.assertEqual(result.also_known_as.first(), alias)  # Ali is alias of Moose

    def test_to_model_invalid_model(self, *_):
        """catch mismatch between activity type and model type"""
        instance = ActivityObject(id="a", type="b")
        with self.assertRaises(ActivitySerializerError):
            instance.to_model(model=models.User)

    @responses.activate
    def test_to_model_image(self, *_):
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
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            activity.to_model(model=models.User, instance=self.user)
        self.assertIsNotNone(self.user.avatar.file)
        self.assertEqual(self.user.name, "New Name")
        self.assertEqual(self.user.key_pair.public_key, "hi")

    def test_to_model_many_to_many(self, *_):
        """annoying that these all need special handling"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
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
                {
                    "type": "Hashtag",
                    "name": "#BookClub",
                    "href": "http://example.com/tags/BookClub",
                },
            ],
        )
        update_data.to_model(model=models.Status, instance=status)
        self.assertEqual(status.mention_users.first(), self.user)
        self.assertEqual(status.mention_books.first(), book)

        hashtag = models.Hashtag.objects.filter(name="#BookClub").first()
        self.assertIsNotNone(hashtag)
        self.assertEqual(status.mention_hashtags.first(), hashtag)

    @responses.activate
    def test_to_model_one_to_many(self, *_):
        """these are reversed relationships, where the secondary object
        keys the primary object but not vice versa"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
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
        with (
            patch("bookwyrm.activitypub.base_activity.set_related_field.delay"),
            patch("bookwyrm.models.status.Status.ignore_activity") as discarder,
        ):
            discarder.return_value = False
            update_data.to_model(model=models.Status, instance=status)
        self.assertIsNone(status.attachments.first())

    @responses.activate
    def test_set_related_field(self, *_):
        """celery task to add back-references to created objects"""
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
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

    @responses.activate
    def test_do_not_raise_error_on_410(self, *_):
        """test that 410 errors are merely logged as a warning"""

        # mock a 410 response
        responses.add(
            responses.GET,
            "https://example.com/user/mouse",
            json=self.userdata,
            status=410,
        )

        # let's check that we actually do get an error in the underlying function
        with self.assertRaises(HTTPError):
            get_activitypub_data("https://example.com/user/mouse")

        # should log a warning
        with self.assertLogs(level="DEBUG") as logger:
            resolved = resolve_remote_id("https://example.com/user/mouse")
            self.assertEqual(
                logger.output,
                [
                    "WARNING:bookwyrm.activitypub.base_activity:request for object dropped because it is gone (410) - remote_id: https://example.com/user/mouse"  # pylint: disable=line-too-long
                ],
            )

            # should not raise an exception
            self.assertEqual(resolved, None)

        # should log nothing if we only want to log errors
        with self.assertNoLogs(logger=None, level="ERROR") as logger:
            resolved = resolve_remote_id("https://example.com/user/mouse")
