"""test author serializer"""

from unittest.mock import patch
import responses

from django.test import TestCase
from bookwyrm import activitypub, models
from bookwyrm.activitypub.base_activity import set_related_field


class TestSeries(TestCase):
    """serialize author tests"""

    @classmethod
    def setUpTestData(cls):
        """initial data"""
        cls.user = models.User.objects.create_user(
            "instance",
            "instance@example.example",
            "pass",
            local=True,
            localname="instance",
        )

        cls.user.remote_id = ("https://example.com/user/instance",)
        cls.user.save(broadcast=False)

        cls.series = models.Series.objects.create(
            user=cls.user,
            name="Example Series",
            alternative_names=["Exemple de série", "Esimerkkisarja"],
            remote_id="https://example.com/series/1",
        )

        cls.book = models.Work.objects.create(
            title="Example Book",
            remote_id="https://example.com/book/1",
        )

        cls.seriesbook = models.SeriesBook.objects.create(
            book=cls.book,
            series=cls.series,
            series_number="1",
            user=cls.user,
            remote_id="https://example.com/seriesbook/1",
        )

        cls.book_data = {
            "id": "https://example.com/book/2",
            "type": "Work",
            "title": "Example Book 2",
            "description": "",
            "languages": [],
            "series": "",
            "seriesNumber": "",
            "seriesBooks": ["https://example.com/seriesbook/2"],
            "subjects": [],
            "subjectPlaces": [],
            "authors": [],
            "firstPublishedDate": "",
            "publishedDate": "",
            "fileLinks": [],
            "lccn": "",
            "editions": [],
            "@context": [
                "https://www.w3.org/ns/activitystreams",
                {"Hashtag": "as:Hashtag"},
            ],
        }

        cls.series_data = {
            "id": "https://example.com/series/2",
            "type": "Series",
            "totalItems": 1,
            "first": "https://example.com/series/2?page=1",
            "last": "https://example.com/series/2?page=1",
            "actor": "https://example.com/user/instance",
            "name": "Example Series 2",
            "alternativeNames": ["Exemple de série 2", "Esimerkkisarja 2"],
            "seriesBooks": ["https://example.com/seriesbook/2"],
            "@context": [
                "https://www.w3.org/ns/activitystreams",
                {"Hashtag": "as:Hashtag"},
            ],
        }

        cls.seriesbook_data = {
            "id": "https://example.com/seriesbook/2",
            "type": "SeriesBook",
            "actor": "https://example.com/user/instance",
            "book": "https://example.com/book/2",
            "series": "https://example.com/series/2",
            "seriesNumber": "99",
            "@context": [
                "https://www.w3.org/ns/activitystreams",
                {"Hashtag": "as:Hashtag"},
            ],
        }

    def test_serialize_series(self):
        """check presence of series fields"""
        activity = self.series.to_activity()

        self.assertEqual(activity["id"], self.series.remote_id)
        self.assertIsInstance(activity["alternativeNames"], list)
        self.assertEqual(
            activity["alternativeNames"], ["Exemple de série", "Esimerkkisarja"]
        )
        self.assertEqual(activity["name"], "Example Series")

    def test_serialize_seriesbook(self):
        """check presence of seriesbook fields"""
        activity = self.seriesbook.to_activity()

        self.assertEqual(activity["book"], self.book.remote_id)
        self.assertEqual(activity["series"], self.series.remote_id)

    @responses.activate
    def test_deserialize_book_with_series(self):
        """check that new style series are deserialised"""

        responses.add(
            responses.GET,
            "https://example.com/series/2",
            json=self.series_data,
            status=200,
        )

        responses.add(
            responses.GET,
            "https://example.com/seriesbook/2",
            json=self.seriesbook_data,
            status=200,
        )

        responses.add(
            responses.GET,
            "https://example.com/user/instance",
            json=self.user.to_activity(),
            status=200,
        )

        self.assertFalse(models.Work.objects.filter(title="Example Book 2").exists())
        self.assertFalse(models.Series.objects.filter(name="Example Series 2").exists())
        self.assertEqual(models.Series.objects.count(), 1)
        self.assertEqual(models.Book.objects.count(), 1)

        book_data = activitypub.Work(**self.book_data)
        book = book_data.to_model()
        with patch(
            "bookwyrm.activitypub.base_activity.set_related_field.delay",
            new=lambda *args: set_related_field(*args),
        ) as mocked:
            book_data.to_model()  # run it again to set the related field

        self.assertEqual(book.title, "Example Book 2")
        self.assertTrue(models.Series.objects.filter(name="Example Series 2").exists())
        self.assertEqual(models.Series.objects.count(), 2)
        self.assertEqual(models.Book.objects.count(), 2)
