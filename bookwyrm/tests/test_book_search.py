""" test searching for books """
import datetime
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from bookwyrm import book_search, models
from bookwyrm.connectors.abstract_connector import AbstractMinimalConnector


class BookSearch(TestCase):
    """look for some books"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.work = models.Work.objects.create(title="Example Work")

        self.first_edition = models.Edition.objects.create(
            title="Example Edition",
            parent_work=self.work,
            isbn_10="0000000000",
            physical_format="Paperback",
            published_date=datetime.datetime(2019, 4, 9, 0, 0, tzinfo=timezone.utc),
        )
        self.second_edition = models.Edition.objects.create(
            title="Another Edition",
            parent_work=self.work,
            isbn_10="1111111111",
            openlibrary_key="hello",
        )

        self.third_edition = models.Edition.objects.create(
            title="Edition with annoying ISBN",
            parent_work=self.work,
            isbn_10="022222222X",
        )

    def test_search(self):
        """search for a book in the db"""
        # title/author
        results = book_search.search("Example")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], self.first_edition)

        # isbn
        results = book_search.search("0000000000")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], self.first_edition)

        # identifier
        results = book_search.search("hello")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], self.second_edition)

    def test_isbn_search(self):
        """test isbn search"""
        results = book_search.isbn_search("0000000000")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], self.first_edition)

    def test_search_identifiers(self):
        """search by unique identifiers"""
        results = book_search.search_identifiers("hello")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], self.second_edition)

    def test_search_identifiers_isbn_search(self):
        """search by unique ID with slightly wonky ISBN"""
        results = book_search.search_identifiers("22222222x")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], self.third_edition)

    def test_search_identifiers_return_first(self):
        """search by unique identifiers"""
        result = book_search.search_identifiers("hello", return_first=True)
        self.assertEqual(result, self.second_edition)

    def test_search_title_author(self):
        """search by unique identifiers"""
        results = book_search.search_title_author("Another", min_confidence=0)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], self.second_edition)

    def test_search_title_author_return_first(self):
        """search by unique identifiers"""
        results = book_search.search_title_author(
            "Another", min_confidence=0, return_first=True
        )
        self.assertEqual(results, self.second_edition)

    def test_format_search_result(self):
        """format a search result"""
        result = book_search.format_search_result(self.first_edition)
        self.assertEqual(result["title"], "Example Edition")
        self.assertEqual(result["key"], self.first_edition.remote_id)
        self.assertEqual(result["year"], 2019)

        result = book_search.format_search_result(self.second_edition)
        self.assertEqual(result["title"], "Another Edition")
        self.assertEqual(result["key"], self.second_edition.remote_id)
        self.assertIsNone(result["year"])

    def test_search_result(self):
        """a class that stores info about a search result"""
        models.Connector.objects.create(
            identifier="example.com",
            connector_file="openlibrary",
            base_url="https://example.com",
            books_url="https://example.com/books",
            covers_url="https://example.com/covers",
            search_url="https://example.com/search?q=",
            isbn_search_url="https://example.com/isbn?q=",
        )

        class TestConnector(AbstractMinimalConnector):
            """nothing added here"""

            def get_or_create_book(self, remote_id):
                pass

            def parse_search_data(self, data, min_confidence):
                return data

            def parse_isbn_search_data(self, data):
                return data

        test_connector = TestConnector("example.com")
        result = book_search.SearchResult(
            title="Title",
            key="https://example.com/book/1",
            author="Author Name",
            year="1850",
            connector=test_connector,
        )
        # there's really not much to test here, it's just a dataclass
        self.assertEqual(result.confidence, 1)
        self.assertEqual(result.title, "Title")


class SearchVectorTriggers(TestCase):
    """look for books as they change"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.work = models.Work.objects.create(title="This Work")
        self.author = models.Author.objects.create(name="Name")
        self.edition = models.Edition.objects.create(
            title="First Edition of Work",
            subtitle="Some Extra Words Are Good",
            series="A Fabulous Sequence of Items",
            parent_work=self.work,
            isbn_10="0000000000",
        )
        self.edition.authors.add(self.author)
        self.edition.save(broadcast=False)

    @classmethod
    def setUpTestData(cls):
        """create conditions that trigger known old bugs"""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                ALTER SEQUENCE bookwyrm_author_id_seq       RESTART WITH 20;
                ALTER SEQUENCE bookwyrm_book_authors_id_seq RESTART WITH 300;
                """
            )

    def test_search_after_changed_metadata(self):
        """book found after updating metadata"""
        self.assertEqual(self.edition, self._search_first("First"))  # title
        self.assertEqual(self.edition, self._search_first("Good"))  # subtitle
        self.assertEqual(self.edition, self._search_first("Sequence"))  # series

        self.edition.title = "Second Title of Work"
        self.edition.subtitle = "Fewer Words Is Better"
        self.edition.series = "A Wondrous Bunch"
        self.edition.save(broadcast=False)

        self.assertEqual(self.edition, self._search_first("Second"))  # title new
        self.assertEqual(self.edition, self._search_first("Fewer"))  # subtitle new
        self.assertEqual(self.edition, self._search_first("Wondrous"))  # series new

        self.assertFalse(self._search_first("First"))  # title old
        self.assertFalse(self._search_first("Good"))  # subtitle old
        self.assertFalse(self._search_first("Sequence"))  # series old

    def test_search_after_author_remove(self):
        """book not found via removed author"""
        self.assertEqual(self.edition, self._search_first("Name"))

        self.edition.authors.set([])
        self.edition.save(broadcast=False)

        self.assertFalse(self._search("Name"))
        self.assertEqual(self.edition, self._search_first("Edition"))

    def test_search_after_author_add(self):
        """book found by newly-added author"""
        new_author = models.Author.objects.create(name="Mozilla")

        self.assertFalse(self._search("Mozilla"))

        self.edition.authors.add(new_author)
        self.edition.save(broadcast=False)

        self.assertEqual(self.edition, self._search_first("Mozilla"))
        self.assertEqual(self.edition, self._search_first("Name"))

    def test_search_after_updated_author_name(self):
        """book found under new author name"""
        self.assertEqual(self.edition, self._search_first("Name"))
        self.assertFalse(self._search("Identifier"))

        self.author.name = "Identifier"
        self.author.save(broadcast=False)

        self.assertFalse(self._search("Name"))
        self.assertEqual(self.edition, self._search_first("Identifier"))
        self.assertEqual(self.edition, self._search_first("Work"))

    def _search_first(self, query):
        """wrapper around search_title_author"""
        return self._search(query, return_first=True)

    # pylint: disable-next=no-self-use
    def _search(self, query, *, return_first=False):
        """wrapper around search_title_author"""
        return book_search.search_title_author(
            query, min_confidence=0, return_first=return_first
        )
