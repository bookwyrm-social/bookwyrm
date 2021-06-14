""" quotation activty object serializer class """
import json
import pathlib
from unittest.mock import patch

from django.test import TestCase
from bookwyrm import activitypub, models


class Quotation(TestCase):
    """we have hecka ways to create statuses"""

    def setUp(self):
        """model objects we'll need"""
        with patch("bookwyrm.models.user.set_remote_server.delay"):
            self.user = models.User.objects.create_user(
                "mouse",
                "mouse@mouse.mouse",
                "mouseword",
                local=False,
                inbox="https://example.com/user/mouse/inbox",
                outbox="https://example.com/user/mouse/outbox",
                remote_id="https://example.com/user/mouse",
            )
        self.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
        )
        datafile = pathlib.Path(__file__).parent.joinpath("../data/ap_quotation.json")
        self.status_data = json.loads(datafile.read_bytes())

    def test_quotation_activity(self):
        """create a Quoteation ap object from json"""
        quotation = activitypub.Quotation(**self.status_data)

        self.assertEqual(quotation.type, "Quotation")
        self.assertEqual(quotation.id, "https://example.com/user/mouse/quotation/13")
        self.assertEqual(quotation.content, "commentary")
        self.assertEqual(quotation.quote, "quote body")
        self.assertEqual(quotation.inReplyToBook, "https://example.com/book/1")
        self.assertEqual(quotation.published, "2020-05-10T02:38:31.150343+00:00")

    def test_activity_to_model(self):
        """create a model instance from an activity object"""
        activity = activitypub.Quotation(**self.status_data)
        quotation = activity.to_model(model=models.Quotation)

        self.assertEqual(quotation.book, self.book)
        self.assertEqual(quotation.user, self.user)
