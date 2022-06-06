""" testing models """
import datetime
import json
import pathlib
from unittest.mock import patch

from django.utils import timezone
from django.test import TestCase
import responses

from bookwyrm import models
from bookwyrm.book_search import SearchResult
from bookwyrm.connectors import connector_manager


class ImportJob(TestCase):
    """this is a fancy one!!!"""

    def setUp(self):
        """data is from a goodreads export of The Raven Tower"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "password", local=True
            )
        self.job = models.ImportJob.objects.create(user=self.local_user, mappings={})

    def test_isbn(self):
        """it unquotes the isbn13 field from data"""
        item = models.ImportItem.objects.create(
            index=1,
            job=self.job,
            data={},
            normalized_data={
                "isbn_13": '="9780356506999"',
            },
        )
        self.assertEqual(item.isbn, "9780356506999")

    def test_shelf(self):
        """converts to the local shelf typology"""
        item = models.ImportItem.objects.create(
            index=1,
            job=self.job,
            data={},
            normalized_data={
                "isbn_13": '="9780356506999"',
                "shelf": "reading",
            },
        )
        self.assertEqual(item.shelf, "reading")

    def test_date_added(self):
        """converts to the local shelf typology"""
        expected = datetime.datetime(2019, 4, 9, 0, 0, tzinfo=timezone.utc)
        item = models.ImportItem.objects.create(
            index=1,
            job=self.job,
            data={},
            normalized_data={
                "isbn_13": '="9780356506999"',
                "shelf": "reading",
                "date_added": "2019/04/09",
            },
        )
        self.assertEqual(item.date_added, expected)

    def test_date_read(self):
        """converts to the local shelf typology"""
        expected = datetime.datetime(2019, 4, 12, 0, 0, tzinfo=timezone.utc)
        item = models.ImportItem.objects.create(
            index=1,
            job=self.job,
            data={},
            normalized_data={
                "isbn_13": '="9780356506999"',
                "shelf": "reading",
                "date_added": "2019/04/09",
                "date_finished": "2019/04/12",
            },
        )
        self.assertEqual(item.date_read, expected)

    def test_currently_reading_reads(self):
        """infer currently reading dates where available"""
        expected = [
            models.ReadThrough(
                start_date=datetime.datetime(2019, 4, 9, 0, 0, tzinfo=timezone.utc)
            )
        ]
        item = models.ImportItem.objects.create(
            index=1,
            job=self.job,
            data={},
            normalized_data={
                "isbn_13": '="9780356506999"',
                "shelf": "reading",
                "date_added": "2019/04/09",
            },
        )
        self.assertEqual(item.reads[0].start_date, expected[0].start_date)
        self.assertIsNone(item.reads[0].finish_date)

    def test_read_reads(self):
        """infer read dates where available"""
        item = models.ImportItem.objects.create(
            index=1,
            job=self.job,
            data={},
            normalized_data={
                "isbn_13": '="9780356506999"',
                "shelf": "reading",
                "date_added": "2019/04/09",
                "date_finished": "2019/04/12",
            },
        )
        self.assertEqual(
            item.reads[0].start_date,
            datetime.datetime(2019, 4, 9, 0, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(
            item.reads[0].finish_date,
            datetime.datetime(2019, 4, 12, 0, 0, tzinfo=timezone.utc),
        )

    def test_unread_reads(self):
        """handle books with no read dates"""
        expected = []
        item = models.ImportItem.objects.create(
            index=1,
            job=self.job,
            data={},
            normalized_data={
                "isbn_13": '="9780356506999"',
                "shelf": "reading",
            },
        )
        self.assertEqual(item.reads, expected)

    @responses.activate
    def test_get_book_from_identifier(self):
        """search and load books by isbn (9780356506999)"""
        item = models.ImportItem.objects.create(
            index=1,
            job=self.job,
            data={},
            normalized_data={
                "isbn_13": '="9780356506999"',
            },
        )
        connector_info = models.Connector.objects.create(
            identifier="openlibrary.org",
            name="OpenLibrary",
            connector_file="openlibrary",
            base_url="https://openlibrary.org",
            books_url="https://openlibrary.org",
            covers_url="https://covers.openlibrary.org",
            search_url="https://openlibrary.org/search?q=",
            priority=3,
        )
        connector = connector_manager.load_connector(connector_info)
        result = SearchResult(
            title="Test Result",
            key="https://openlibrary.org/works/OL1234W",
            author="An Author",
            year="1980",
            connector=connector,
        )

        datafile = pathlib.Path(__file__).parent.joinpath("../data/ol_edition.json")
        bookdata = json.loads(datafile.read_bytes())
        responses.add(
            responses.GET,
            "https://openlibrary.org/works/OL1234W",
            json=bookdata,
            status=200,
        )
        responses.add(
            responses.GET,
            "https://openlibrary.org/works/OL15832982W",
            json=bookdata,
            status=200,
        )
        responses.add(
            responses.GET,
            "https://openlibrary.org/authors/OL382982A",
            json={"name": "test author"},
            status=200,
        )

        with patch("bookwyrm.connectors.abstract_connector.load_more_data.delay"):
            with patch(
                "bookwyrm.connectors.connector_manager.first_search_result"
            ) as search:
                search.return_value = result
                with patch(
                    "bookwyrm.connectors.openlibrary.Connector.get_authors_from_data"
                ):
                    book = item.get_book_from_identifier()

        self.assertEqual(book.title, "Sabriel")
