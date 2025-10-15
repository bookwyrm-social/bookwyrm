""" testing book data connectors """
import json
import pathlib

from django.test import TestCase
import responses

from bookwyrm import models
from bookwyrm.connectors.finna import Connector, guess_page_numbers


class Finna(TestCase):
    """test loading data from finna.fi"""

    @classmethod
    def setUpTestData(cls):
        """creates the connector in the database"""
        models.Connector.objects.create(
            identifier="api.finna.fi",
            name="Finna API",
            connector_file="finna",
            base_url="https://www.finna.fi",
            books_url="https://api.finna.fi/api/v1/record" "?id=",
            covers_url="https://api.finna.fi",
            search_url="https://api.finna.fi/api/v1/search?limit=20"
            "&filter[]=format%3a%220%2fBook%2f%22"
            "&field[]=title&field[]=recordPage&field[]=authors"
            "&field[]=year&field[]=id&field[]=formats&field[]=images"
            "&lookfor=",
            isbn_search_url="https://api.finna.fi/api/v1/search?limit=1"
            "&filter[]=format%3a%220%2fBook%2f%22"
            "&field[]=title&field[]=recordPage&field[]=authors&field[]=year"
            "&field[]=id&field[]=formats&field[]=images"
            "&lookfor=isbn:",
        )

    def setUp(self):
        """connector instance"""
        self.connector = Connector("api.finna.fi")

    def test_parse_search_data(self):
        """json to search result objs"""
        search_file = pathlib.Path(__file__).parent.joinpath(
            "../data/finna_search.json"
        )
        search_results = json.loads(search_file.read_bytes())
        print(search_results)

        print(self.connector)
        formatted = list(self.connector.parse_search_data(search_results, 0))
        print(formatted)

        self.assertEqual(formatted[0].title, "Sarvijumala")
        self.assertEqual(formatted[0].author, "Magdalena Hai")
        self.assertEqual(
            formatted[0].key, "https://api.finna.fi/api/v1/record?id=anders.1920022"
        )
        self.assertEqual(
            formatted[0].cover,
            None,
        )
        # Test that edition info is parsed correctly to title
        self.assertEqual(formatted[1].title, "Sarvijumala Audiobook")
        self.assertEqual(formatted[2].title, "Sarvijumala")
        self.assertEqual(formatted[3].title, "Sarvijumala eBook")

    def test_parse_isbn_search_data(self):
        """another search type"""
        search_file = pathlib.Path(__file__).parent.joinpath(
            "../data/finna_isbn_search.json"
        )
        search_results = json.loads(search_file.read_bytes())

        formatted = list(self.connector.parse_isbn_search_data(search_results))[0]

        self.assertEqual(formatted.title, "Ilmakirja : painovoimainen ilmanvaihto")
        self.assertEqual(
            formatted.key, "https://api.finna.fi/api/v1/record?id=3amk.308439"
        )

    def test_parse_isbn_search_data_empty(self):
        """another search type"""
        search_results = {"resultCount": 0, "records": []}
        results = list(self.connector.parse_isbn_search_data(search_results))
        self.assertEqual(results, [])

    def test_page_count_parsing(self):
        """Test page count parsing flow"""
        for data in [
            "123 sivua",
            "123, [4] sivua",
            "sidottu 123 sivua",
            "123s; [4]; 9cm",
        ]:
            page_count = guess_page_numbers([data])
            self.assertEqual(page_count, "123")
        for data in [" sivua", "xx, [4] sivua", "sidottu", "[4]; 9cm"]:
            page_count = guess_page_numbers([data])
            self.assertEqual(page_count, None)

    @responses.activate
    def test_get_book_data(self):
        """Test book data parsing from example json files"""
        record_file = pathlib.Path(__file__).parent.joinpath(
            "../data/finna_record.json"
        )
        version_file = pathlib.Path(__file__).parent.joinpath(
            "../data/finna_versions.json"
        )
        author_file = pathlib.Path(__file__).parent.joinpath(
            "../data/finna_author_search.json"
        )
        record_result = json.loads(record_file.read_bytes())
        versions_result = json.loads(version_file.read_bytes())
        author_search_result = json.loads(author_file.read_bytes())
        responses.add(
            responses.GET,
            "https://api.finna.fi/api/v1/search?id=anders.1819084&search=versions"
            "&view=&field%5B%5D=authors&field%5B%5D=cleanIsbn&field%5B%5D=edition"
            "&field%5B%5D=formats&field%5B%5D=id&field%5B%5D=images&field%5B%5D=isbns"
            "&field%5B%5D=languages&field%5B%5D=physicalDescriptions"
            "&field%5B%5D=publishers&field%5B%5D=recordPage&field%5B%5D=series"
            "&field%5B%5D=shortTitle&field%5B%5D=subjects&field%5B%5D=subTitle"
            "&field%5B%5D=summary&field%5B%5D=title&field%5B%5D=year",
            json=versions_result,
        )
        responses.add(
            responses.GET,
            "https://api.finna.fi/api/v1/search?limit=20&filter%5B%5D=format%3A%220%2F"
            "Book%2F%22&field%5B%5D=title&field%5B%5D=recordPage&field%5B%5D=authors&"
            "field%5B%5D=year&field%5B%5D=id&field%5B%5D=formats&field%5B%5D=images&"
            "lookfor=Emmi%20It%C3%A4ranta&type=Author&field%5B%5D=authors&field%5B%5D"
            "=cleanIsbn&field%5B%5D=formats&field%5B%5D=id&field%5B%5D=images&field"
            "%5B%5D=isbns&field%5B%5D=languages&field%5B%5D=physicalDescriptions&"
            "field%5B%5D=publishers&field%5B%5D=recordPage&field%5B%5D=series&field"
            "%5B%5D=shortTitle&field%5B%5D=subjects&field%5B%5D=subTitle"
            "&field%5B%5D=summary&field%5B%5D=title&field%5B%5D=year",
            json=author_search_result,
        )
        responses.add(responses.GET, "https://test.url/id", json=record_result)
        book = self.connector.get_or_create_book("https://test.url/id")
        self.assertEqual(book.languages[0], "Finnish")
