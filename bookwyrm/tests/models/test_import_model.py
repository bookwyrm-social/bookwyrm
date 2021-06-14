""" testing models """
import datetime
import json
import pathlib
from unittest.mock import patch

from django.utils import timezone
from django.test import TestCase
import responses

from bookwyrm import models
from bookwyrm.connectors import connector_manager
from bookwyrm.connectors.abstract_connector import SearchResult


class ImportJob(TestCase):
    """this is a fancy one!!!"""

    def setUp(self):
        """data is from a goodreads export of The Raven Tower"""
        read_data = {
            "Book Id": 39395857,
            "Title": "The Raven Tower",
            "Author": "Ann Leckie",
            "Author l-f": "Leckie, Ann",
            "Additional Authors": "",
            "ISBN": '="0356506991"',
            "ISBN13": '="9780356506999"',
            "My Rating": 0,
            "Average Rating": 4.06,
            "Publisher": "Orbit",
            "Binding": "Hardcover",
            "Number of Pages": 416,
            "Year Published": 2019,
            "Original Publication Year": 2019,
            "Date Read": "2019/04/12",
            "Date Added": "2019/04/09",
            "Bookshelves": "",
            "Bookshelves with positions": "",
            "Exclusive Shelf": "read",
            "My Review": "",
            "Spoiler": "",
            "Private Notes": "",
            "Read Count": 1,
            "Recommended For": "",
            "Recommended By": "",
            "Owned Copies": 0,
            "Original Purchase Date": "",
            "Original Purchase Location": "",
            "Condition": "",
            "Condition Description": "",
            "BCID": "",
        }
        currently_reading_data = read_data.copy()
        currently_reading_data["Exclusive Shelf"] = "currently-reading"
        currently_reading_data["Date Read"] = ""

        unknown_read_data = currently_reading_data.copy()
        unknown_read_data["Exclusive Shelf"] = "read"
        unknown_read_data["Date Read"] = ""

        user = models.User.objects.create_user(
            "mouse", "mouse@mouse.mouse", "mouseword", local=True, localname="mouse"
        )
        job = models.ImportJob.objects.create(user=user)
        self.item_1 = models.ImportItem.objects.create(
            job=job, index=1, data=currently_reading_data
        )
        self.item_2 = models.ImportItem.objects.create(job=job, index=2, data=read_data)
        self.item_3 = models.ImportItem.objects.create(
            job=job, index=3, data=unknown_read_data
        )

    def test_isbn(self):
        """it unquotes the isbn13 field from data"""
        expected = "9780356506999"
        item = models.ImportItem.objects.get(index=1)
        self.assertEqual(item.isbn, expected)

    def test_shelf(self):
        """converts to the local shelf typology"""
        expected = "reading"
        self.assertEqual(self.item_1.shelf, expected)

    def test_date_added(self):
        """converts to the local shelf typology"""
        expected = datetime.datetime(2019, 4, 9, 0, 0, tzinfo=timezone.utc)
        item = models.ImportItem.objects.get(index=1)
        self.assertEqual(item.date_added, expected)

    def test_date_read(self):
        """converts to the local shelf typology"""
        expected = datetime.datetime(2019, 4, 12, 0, 0, tzinfo=timezone.utc)
        item = models.ImportItem.objects.get(index=2)
        self.assertEqual(item.date_read, expected)

    def test_currently_reading_reads(self):
        """infer currently reading dates where available"""
        expected = [
            models.ReadThrough(
                start_date=datetime.datetime(2019, 4, 9, 0, 0, tzinfo=timezone.utc)
            )
        ]
        actual = models.ImportItem.objects.get(index=1)
        self.assertEqual(actual.reads[0].start_date, expected[0].start_date)
        self.assertEqual(actual.reads[0].finish_date, expected[0].finish_date)

    def test_read_reads(self):
        """infer read dates where available"""
        actual = self.item_2
        self.assertEqual(
            actual.reads[0].start_date,
            datetime.datetime(2019, 4, 9, 0, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(
            actual.reads[0].finish_date,
            datetime.datetime(2019, 4, 12, 0, 0, tzinfo=timezone.utc),
        )

    def test_unread_reads(self):
        """handle books with no read dates"""
        expected = []
        actual = models.ImportItem.objects.get(index=3)
        self.assertEqual(actual.reads, expected)

    @responses.activate
    def test_get_book_from_isbn(self):
        """search and load books by isbn (9780356506999)"""
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
                    "bookwyrm.connectors.openlibrary.Connector." "get_authors_from_data"
                ):
                    book = self.item_1.get_book_from_isbn()

        self.assertEqual(book.title, "Sabriel")
