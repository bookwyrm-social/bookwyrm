"""testing Libris book data connector"""

import json
import pathlib

from django.test import TestCase

from bookwyrm import models
from bookwyrm.connectors.libris import (
    Connector,
    extract_id_from_url,
    format_authors_for_display,
    get_first,
    get_first_author_name,
    join_paragraphs,
    parse_author_name,
    parse_authors,
    parse_isbn10,
    parse_isbn13,
    parse_publishers,
    resolve_languages,
)


class LibrisConnector(TestCase):
    """test loading data from libris.kb.se"""

    @classmethod
    def setUpTestData(cls):
        """creates the connector in the database"""
        models.Connector.objects.create(
            identifier="libris.kb.se",
            name="Libris",
            connector_file="libris",
            base_url="https://libris.kb.se",
            books_url="http://libris.kb.se/xsearch?format=json&n=1&query=",
            covers_url="",
            search_url="http://libris.kb.se/xsearch?format=json&n=20&query=",
            isbn_search_url="http://libris.kb.se/xsearch?format=json&n=5&query=isbn:",
        )

    def setUp(self):
        """connector instance"""
        self.connector = Connector("libris.kb.se")

    def test_parse_search_data(self):
        """json to search result objs"""
        search_file = pathlib.Path(__file__).parent.joinpath(
            "../data/libris_search.json"
        )
        search_results = json.loads(search_file.read_bytes())

        formatted = list(self.connector.parse_search_data(search_results, 0))

        self.assertEqual(len(formatted), 5)
        self.assertEqual(
            formatted[0].title,
            "Känner du Astrid Lindgren? : berättelsen om Astrids liv",
        )
        self.assertEqual(formatted[0].author, "David Sundin; Amanda Berglund")
        self.assertEqual(formatted[0].key, "http://libris.kb.se/bib/6rkftbcz44gf3pqm")
        self.assertIsNone(formatted[0].cover)  # Libris doesn't provide covers
        self.assertEqual(formatted[0].year, "2025")
        self.assertEqual(formatted[0].confidence, 1.0)

    def test_parse_search_data_min_confidence(self):
        """test that min_confidence threshold filters results"""
        search_file = pathlib.Path(__file__).parent.joinpath(
            "../data/libris_search.json"
        )
        search_results = json.loads(search_file.read_bytes())

        formatted = list(self.connector.parse_search_data(search_results, 0.5))
        self.assertEqual(len(formatted), 2)

        formatted = list(self.connector.parse_search_data(search_results, 0.25))
        self.assertEqual(len(formatted), 4)

        formatted = list(self.connector.parse_search_data(search_results, 1.0))
        self.assertEqual(len(formatted), 1)

    def test_parse_search_data_multiple_authors(self):
        """test parsing search results with multiple authors"""
        search_file = pathlib.Path(__file__).parent.joinpath(
            "../data/libris_search.json"
        )
        search_results = json.loads(search_file.read_bytes())

        formatted = list(self.connector.parse_search_data(search_results, 0))

        # the fourth record has four authors
        self.assertEqual(
            formatted[3].title, "Allrakäraste Astrid : en vänbok till Astrid Lindgren"
        )
        self.assertEqual(
            formatted[3].author,
            "Susanna Hellsing; Birgitta Westin; Suzanne Öhman; Astrid Lindgren",
        )

    def test_parse_isbn_search_data(self):
        """test ISBN search parsing"""
        search_file = pathlib.Path(__file__).parent.joinpath(
            "../data/libris_isbn_search.json"
        )
        search_results = json.loads(search_file.read_bytes())

        formatted = list(self.connector.parse_isbn_search_data(search_results))

        self.assertEqual(len(formatted), 1)
        self.assertEqual(
            formatted[0].title,
            "Känner du Astrid Lindgren? : berättelsen om Astrids liv",
        )
        self.assertEqual(formatted[0].key, "http://libris.kb.se/bib/6rkftbcz44gf3pqm")
        self.assertEqual(formatted[0].author, "David Sundin; Amanda Berglund")

    def test_parse_isbn_search_data_empty(self):
        """test empty ISBN search results"""
        search_results = {"xsearch": {"from": 0, "to": 0, "records": 0, "list": []}}
        results = list(self.connector.parse_isbn_search_data(search_results))
        self.assertEqual(results, [])

    def test_parse_search_data_with_trailing_dot_authors(self):
        """test that author names with trailing dots are parsed and deduplicated"""
        search_file = pathlib.Path(__file__).parent.joinpath(
            "../data/libris_search.json"
        )
        search_results = json.loads(search_file.read_bytes())

        formatted = list(self.connector.parse_search_data(search_results, 0))

        # second record has authors with trailing dots, and
        # "Lindgren, Astrid, 1907-2002." appears multiple times
        self.assertEqual(formatted[1].title, "Pippi Langstrømpe")
        self.assertEqual(
            formatted[1].author,
            "Astrid Lindgren; Ingrid Vang Nyman; Hans Braarvig",
        )
        self.assertEqual(formatted[1].author.count("Astrid Lindgren"), 1)

    def test_parse_search_data_with_array_date(self):
        """test that date arrays are handled correctly"""
        search_file = pathlib.Path(__file__).parent.joinpath(
            "../data/libris_search.json"
        )
        search_results = json.loads(search_file.read_bytes())
        formatted = list(self.connector.parse_search_data(search_results, 0))

        # third record has date as a creative array: ["[2024]", "2024"]
        self.assertEqual(
            formatted[2].title, "Den rätta knycken : Astrid Lindgrens Vi på Saltkråkan"
        )
        self.assertEqual(formatted[2].year, "[2024]")

    def test_get_remote_id(self):
        """test getting remote id from data"""
        data = {"identifier": "http://libris.kb.se/bib/abc123"}
        self.assertEqual(
            self.connector.get_remote_id(data), "http://libris.kb.se/bib/abc123"
        )

    def test_get_remote_id_list(self):
        """test getting remote id when identifier is a list"""
        data = {"identifier": ["http://libris.kb.se/bib/abc123", "other"]}
        self.assertEqual(
            self.connector.get_remote_id(data), "http://libris.kb.se/bib/abc123"
        )

    def test_get_remote_id_missing(self):
        """test getting remote id when identifier is missing"""
        data = {}
        self.assertEqual(self.connector.get_remote_id(data), "")
        data = {"identifier": None}
        self.assertEqual(self.connector.get_remote_id(data), "")

    def test_get_remote_id_from_model(self):
        """test constructing remote URL from model with libris_key"""

        class MockModel:
            libris_key = "6rkftbcz44gf3pqm"

        obj = MockModel()
        self.assertEqual(
            self.connector.get_remote_id_from_model(obj),
            "https://libris.kb.se/bib/6rkftbcz44gf3pqm",
        )

    def test_get_remote_id_from_model_no_key(self):
        """test constructing remote URL when model has no libris_key"""

        class MockModel:
            libris_key = None

        obj = MockModel()
        self.assertEqual(self.connector.get_remote_id_from_model(obj), "")


class LibrisHelperFunctions(TestCase):
    """test helper functions in libris connector"""

    def test_extract_id_from_url(self):
        """test extracting libris ID from URL"""
        self.assertEqual(
            extract_id_from_url("http://libris.kb.se/bib/6rkftbcz44gf3pqm"),
            "6rkftbcz44gf3pqm",
        )
        self.assertEqual(
            extract_id_from_url("https://libris.kb.se/bib/abc123"),
            "abc123",
        )
        self.assertIsNone(extract_id_from_url("abc123def"))
        self.assertIsNone(extract_id_from_url("https://other-site.com/book/123"))
        self.assertIsNone(extract_id_from_url(""))
        self.assertIsNone(extract_id_from_url(None))

    def test_get_first(self):
        """test extracting first element from list or returning value as-is"""
        self.assertEqual(get_first(["a", "b", "c"]), "a")
        self.assertEqual(get_first(["only"]), "only")
        self.assertIsNone(get_first([]))
        self.assertEqual(get_first("string"), "string")
        self.assertEqual(get_first(123), 123)
        self.assertIsNone(get_first(None))

    def test_parse_author_name(self):
        """test parsing author names from Libris format"""
        # Standard format: LastName, FirstName, Year-
        self.assertEqual(
            parse_author_name("Lindgren, Astrid, 1907-2002"), "Astrid Lindgren"
        )
        # without death year
        self.assertEqual(parse_author_name("Svensson, Kalle, 1980-"), "Kalle Svensson")
        # without any year
        self.assertEqual(parse_author_name("Karlsson, Erik"), "Erik Karlsson")
        # single name
        self.assertEqual(parse_author_name("Anonymous"), "Anonymous")
        # with trailing dot (yes it happens)
        self.assertEqual(
            parse_author_name("Jansson, Tove, 1914-2001 ."), "Tove Jansson"
        )
        self.assertEqual(
            parse_author_name("Lagerlöf, Selma, 1858-1940."), "Selma Lagerlöf"
        )
        # year with trailing dot and space
        self.assertEqual(
            parse_author_name("Strindberg, August, 1849- ."), "August Strindberg"
        )
        self.assertIsNone(parse_author_name(""))
        self.assertIsNone(parse_author_name(None))

    def test_parse_authors(self):
        """test parsing multiple authors"""
        self.assertEqual(
            parse_authors("Lindgren, Astrid, 1907-2002"), ["Astrid Lindgren"]
        )
        self.assertEqual(
            parse_authors(["Svensson, Kalle, 1980-", "Andersson, Anna, 1985-"]),
            ["Kalle Svensson", "Anna Andersson"],
        )
        self.assertEqual(parse_authors(None), [])
        self.assertEqual(parse_authors(""), [])

    def test_parse_authors_deduplicates(self):
        """test that duplicate authors are removed"""
        creators = [
            "Lindgren, Astrid, 1907-2002",
            "Lindgren, Astrid, 1907-2002.",
            "Lindgren, Astrid, 1907-2002.",
            "Vang Nyman, Ingrid, 1916-1959",
        ]
        result = parse_authors(creators)
        self.assertEqual(result, ["Astrid Lindgren", "Ingrid Vang Nyman"])

    def test_get_first_author_name(self):
        """test getting first author name from creator data"""
        self.assertEqual(
            get_first_author_name("Lindgren, Astrid, 1907-2002"), "Astrid Lindgren"
        )
        self.assertEqual(
            get_first_author_name(["Svensson, Kalle", "Andersson, Anna"]),
            "Kalle Svensson",
        )
        self.assertIsNone(get_first_author_name(None))
        self.assertIsNone(get_first_author_name([]))

    def test_format_authors_for_display(self):
        """test formatting authors for display in search results"""
        self.assertEqual(
            format_authors_for_display("Lindgren, Astrid, 1907-2002"),
            "Astrid Lindgren",
        )
        self.assertEqual(
            format_authors_for_display(["Svensson, Kalle", "Andersson, Anna"]),
            "Kalle Svensson; Anna Andersson",
        )
        self.assertIsNone(format_authors_for_display(None))
        self.assertIsNone(format_authors_for_display([]))

    def test_parse_isbn13(self):
        """test parsing ISBN-13"""
        self.assertEqual(parse_isbn13("9789129748468"), "9789129748468")
        self.assertEqual(parse_isbn13("978-91-29-74846-8"), "9789129748468")
        self.assertEqual(parse_isbn13(["9129657741", "9789129688313"]), "9789129688313")
        self.assertIsNone(parse_isbn13("9129657741"))
        self.assertIsNone(parse_isbn13(None))
        self.assertIsNone(parse_isbn13(""))

    def test_parse_isbn13_rejects_x(self):
        """ISBN-13 must not accept 'X' character (only valid in ISBN-10 check digit)"""
        self.assertIsNone(parse_isbn13("978912974846X"))
        self.assertIsNone(parse_isbn13("97891297X8468"))
        # even if it would be 13 chars with X
        self.assertIsNone(parse_isbn13("978-91-29-7484-X"))

    def test_parse_isbn10(self):
        """test parsing ISBN-10"""
        self.assertEqual(parse_isbn10("9129657741"), "9129657741")
        self.assertEqual(parse_isbn10("91-29-65774-1"), "9129657741")
        self.assertEqual(parse_isbn10(["9789129688313", "9129657741"]), "9129657741")
        self.assertIsNone(parse_isbn10("9789129748468"))
        self.assertIsNone(parse_isbn10(None))
        self.assertIsNone(parse_isbn10(""))

    def test_parse_isbn10_accepts_x(self):
        """ISBN-10 should accept 'X' as valid check digit"""
        self.assertEqual(parse_isbn10("080442957X"), "080442957X")
        self.assertEqual(parse_isbn10("0-8044-2957-X"), "080442957X")
        self.assertEqual(parse_isbn10("080442957x"), "080442957X")

    def test_parse_publishers(self):
        """test parsing publisher field"""
        self.assertEqual(
            parse_publishers("Stockholm : Rabén & Sjögren"), ["Rabén & Sjögren"]
        )
        self.assertEqual(parse_publishers("Bonniers"), ["Bonniers"])
        self.assertEqual(
            parse_publishers(["Stockholm : Förlag A", "Göteborg : Förlag B"]),
            ["Förlag A", "Förlag B"],
        )
        self.assertEqual(parse_publishers(None), [])
        self.assertEqual(parse_publishers(""), [])

    def test_join_paragraphs(self):
        """test joining list elements with newlines"""
        self.assertEqual(join_paragraphs("A single line."), "A single line.")
        self.assertEqual(
            join_paragraphs(["First.", "Second.", "Third."]),
            "First.\nSecond.\nThird.",
        )
        self.assertIsNone(join_paragraphs(None))
        self.assertIsNone(join_paragraphs(""))
        self.assertIsNone(join_paragraphs([]))

    def test_resolve_languages(self):
        """test resolving language codes to language names"""
        # single language
        result = resolve_languages("swe")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], "Swedish")
        # multiple languages
        result = resolve_languages(["swe", "eng"])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], "Swedish")
        self.assertEqual(result[1], "English")
        # unknown language code falls back to the code itself
        result = resolve_languages("xyz")
        self.assertEqual(result, ["xyz"])
        # falsey
        self.assertEqual(resolve_languages(None), [])
        self.assertEqual(resolve_languages(""), [])
