""" openlibrary data connector """
import re

from bookwyrm import models
from .abstract_connector import AbstractConnector, SearchResult, Mapping
from .abstract_connector import get_data
from .connector_manager import ConnectorException
from .openlibrary_languages import languages


class Connector(AbstractConnector):
    """instantiate a connector for OL"""

    def __init__(self, identifier):
        super().__init__(identifier)

        get_first = lambda a, *args: a[0]
        get_remote_id = lambda a, *args: self.base_url + a
        self.book_mappings = [
            Mapping("title"),
            Mapping("id", remote_field="key", formatter=get_remote_id),
            Mapping("cover", remote_field="covers", formatter=self.get_cover_url),
            Mapping("sortTitle", remote_field="sort_title"),
            Mapping("subtitle"),
            Mapping("description", formatter=get_description),
            Mapping("languages", formatter=get_languages),
            Mapping("series", formatter=get_first),
            Mapping("seriesNumber", remote_field="series_number"),
            Mapping("subjects"),
            Mapping("subjectPlaces", remote_field="subject_places"),
            Mapping("isbn13", remote_field="isbn_13", formatter=get_first),
            Mapping("isbn10", remote_field="isbn_10", formatter=get_first),
            Mapping("lccn", formatter=get_first),
            Mapping("oclcNumber", remote_field="oclc_numbers", formatter=get_first),
            Mapping(
                "openlibraryKey", remote_field="key", formatter=get_openlibrary_key
            ),
            Mapping("goodreadsKey", remote_field="goodreads_key"),
            Mapping("asin"),
            Mapping(
                "firstPublishedDate",
                remote_field="first_publish_date",
            ),
            Mapping("publishedDate", remote_field="publish_date"),
            Mapping("pages", remote_field="number_of_pages"),
            Mapping("physicalFormat", remote_field="physical_format"),
            Mapping("publishers"),
        ]

        self.author_mappings = [
            Mapping("id", remote_field="key", formatter=get_remote_id),
            Mapping("name"),
            Mapping(
                "openlibraryKey", remote_field="key", formatter=get_openlibrary_key
            ),
            Mapping("born", remote_field="birth_date"),
            Mapping("died", remote_field="death_date"),
            Mapping("bio", formatter=get_description),
        ]

    def get_book_data(self, remote_id):
        data = get_data(remote_id)
        if data.get("type", {}).get("key") == "/type/redirect":
            remote_id = self.base_url + data.get("location")
            return get_data(remote_id)
        return data

    def get_remote_id_from_data(self, data):
        """format a url from an openlibrary id field"""
        try:
            key = data["key"]
        except KeyError:
            raise ConnectorException("Invalid book data")
        return "%s%s" % (self.books_url, key)

    def is_work_data(self, data):
        return bool(re.match(r"^[\/\w]+OL\d+W$", data["key"]))

    def get_edition_from_work_data(self, data):
        try:
            key = data["key"]
        except KeyError:
            raise ConnectorException("Invalid book data")
        url = "%s%s/editions" % (self.books_url, key)
        data = self.get_book_data(url)
        edition = pick_default_edition(data["entries"])
        if not edition:
            raise ConnectorException("No editions for work")
        return edition

    def get_work_from_edition_data(self, data):
        try:
            key = data["works"][0]["key"]
        except (IndexError, KeyError):
            raise ConnectorException("No work found for edition")
        url = "%s%s" % (self.books_url, key)
        return self.get_book_data(url)

    def get_authors_from_data(self, data):
        """parse author json and load or create authors"""
        for author_blob in data.get("authors", []):
            author_blob = author_blob.get("author", author_blob)
            # this id is "/authors/OL1234567A"
            author_id = author_blob["key"]
            url = "%s%s" % (self.base_url, author_id)
            author = self.get_or_create_author(url)
            if not author:
                continue
            yield author

    def get_cover_url(self, cover_blob, size="L"):
        """ask openlibrary for the cover"""
        if not cover_blob:
            return None
        cover_id = cover_blob[0]
        image_name = "%s-%s.jpg" % (cover_id, size)
        return "%s/b/id/%s" % (self.covers_url, image_name)

    def parse_search_data(self, data):
        return data.get("docs")

    def format_search_result(self, search_result):
        # build the remote id from the openlibrary key
        key = self.books_url + search_result["key"]
        author = search_result.get("author_name") or ["Unknown"]
        cover_blob = search_result.get("cover_i")
        cover = self.get_cover_url([cover_blob], size="M") if cover_blob else None
        return SearchResult(
            title=search_result.get("title"),
            key=key,
            author=", ".join(author),
            connector=self,
            year=search_result.get("first_publish_year"),
            cover=cover,
        )

    def parse_isbn_search_data(self, data):
        return list(data.values())

    def format_isbn_search_result(self, search_result):
        # build the remote id from the openlibrary key
        key = self.books_url + search_result["key"]
        authors = search_result.get("authors") or [{"name": "Unknown"}]
        author_names = [author.get("name") for author in authors]
        return SearchResult(
            title=search_result.get("title"),
            key=key,
            author=", ".join(author_names),
            connector=self,
            year=search_result.get("publish_date"),
        )

    def load_edition_data(self, olkey):
        """query openlibrary for editions of a work"""
        url = "%s/works/%s/editions" % (self.books_url, olkey)
        return self.get_book_data(url)

    def expand_book_data(self, book):
        work = book
        # go from the edition to the work, if necessary
        if isinstance(book, models.Edition):
            work = book.parent_work

        # we can mass download edition data from OL to avoid repeatedly querying
        try:
            edition_options = self.load_edition_data(work.openlibrary_key)
        except ConnectorException:
            # who knows, man
            return

        for edition_data in edition_options.get("entries"):
            # does this edition have ANY interesting data?
            if ignore_edition(edition_data):
                continue
            self.create_edition_from_data(work, edition_data)


def ignore_edition(edition_data):
    """don't load a million editions that have no metadata"""
    # an isbn, we love to see it
    if edition_data.get("isbn_13") or edition_data.get("isbn_10"):
        return False
    # grudgingly, oclc can stay
    if edition_data.get("oclc_numbers"):
        return False
    # if it has a cover it can stay
    if edition_data.get("covers"):
        return False
    # keep non-english editions
    if edition_data.get("languages") and "languages/eng" not in str(
        edition_data.get("languages")
    ):
        return False
    return True


def get_description(description_blob):
    """descriptions can be a string or a dict"""
    if isinstance(description_blob, dict):
        return description_blob.get("value")
    return description_blob


def get_openlibrary_key(key):
    """convert /books/OL27320736M into OL27320736M"""
    return key.split("/")[-1]


def get_languages(language_blob):
    """/language/eng -> English"""
    langs = []
    for lang in language_blob:
        langs.append(languages.get(lang.get("key", ""), None))
    return langs


def pick_default_edition(options):
    """favor physical copies with covers in english"""
    if not options:
        return None
    if len(options) == 1:
        return options[0]

    options = [e for e in options if e.get("covers")] or options
    options = [
        e for e in options if "/languages/eng" in str(e.get("languages"))
    ] or options
    formats = ["paperback", "hardcover", "mass market paperback"]
    options = [
        e for e in options if str(e.get("physical_format")).lower() in formats
    ] or options
    options = [e for e in options if e.get("isbn_13")] or options
    options = [e for e in options if e.get("ocaid")] or options
    return options[0]
