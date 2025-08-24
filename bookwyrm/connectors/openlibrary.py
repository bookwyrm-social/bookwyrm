""" openlibrary data connector """
import re
from typing import Any, Optional, Union, Iterator, Iterable

from markdown import markdown

from bookwyrm import models
from bookwyrm.book_search import SearchResult
from bookwyrm.utils.sanitizer import clean
from .abstract_connector import AbstractConnector, Mapping, JsonDict
from .abstract_connector import get_data, infer_physical_format, unique_physical_format
from .connector_manager import ConnectorException, create_edition_task
from .openlibrary_languages import languages


class Connector(AbstractConnector):
    """instantiate a connector for OL"""

    generated_remote_link_field = "openlibrary_link"

    def __init__(self, identifier: str):
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
            Mapping("series", formatter=parse_series),
            Mapping(
                "seriesNumber",
                remote_field="series",
                formatter=parse_series_number,
            ),
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
            Mapping(
                "physicalFormat",
                remote_field="physical_format",
                formatter=infer_physical_format,
            ),
            Mapping(
                "physicalFormatDetail",
                remote_field="physical_format",
                formatter=unique_physical_format,
            ),
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
            Mapping(
                "isni",
                remote_field="remote_ids",
                formatter=lambda b: get_dict_field(b, "isni"),
            ),
            Mapping(
                "asin",
                remote_field="remote_ids",
                formatter=lambda b: get_dict_field(b, "amazon"),
            ),
            Mapping(
                "viaf",
                remote_field="remote_ids",
                formatter=lambda b: get_dict_field(b, "viaf"),
            ),
            Mapping(
                "wikidata",
                remote_field="remote_ids",
                formatter=lambda b: get_dict_field(b, "wikidata"),
            ),
            Mapping(
                "wikipedia_link", remote_field="links", formatter=get_wikipedia_link
            ),
            Mapping("inventaire_id", remote_field="links", formatter=get_inventaire_id),
        ]

    def get_book_data(self, remote_id: str) -> JsonDict:
        data = get_data(remote_id)
        if data.get("type", {}).get("key") == "/type/redirect":
            remote_id = self.base_url + data.get("location", "")
            return get_data(remote_id)
        return data

    def get_remote_id_from_data(self, data: JsonDict) -> str:
        """format a url from an openlibrary id field"""
        try:
            key = data["key"]
        except KeyError:
            raise ConnectorException("Invalid book data")
        return f"{self.books_url}{key}"

    def is_work_data(self, data: JsonDict) -> bool:
        return bool(re.match(r"^[\/\w]+OL\d+W$", data["key"]))

    def get_edition_from_work_data(self, data: JsonDict) -> JsonDict:
        try:
            key = data["key"]
        except KeyError:
            raise ConnectorException("Invalid book data")
        url = f"{self.books_url}{key}/editions"
        data = self.get_book_data(url)
        edition = pick_default_edition(data["entries"])
        if not edition:
            raise ConnectorException("No editions for work")
        return edition

    def get_work_from_edition_data(self, data: JsonDict) -> JsonDict:
        try:
            key = data["works"][0]["key"]
        except (IndexError, KeyError):
            raise ConnectorException("No work found for edition")
        url = f"{self.books_url}{key}"
        return self.get_book_data(url)

    def get_authors_from_data(self, data: JsonDict) -> Iterator[models.Author]:
        """parse author json and load or create authors"""
        for author_blob in data.get("authors", []):
            author_blob = author_blob.get("author", author_blob)
            # this id is "/authors/OL1234567A"
            author_id = author_blob["key"]
            url = f"{self.base_url}{author_id}"
            author = self.get_or_create_author(url)
            if not author:
                continue
            yield author

    def get_cover_url(self, cover_blob: list[str], size: str = "L") -> Optional[str]:
        """ask openlibrary for the cover"""
        if not cover_blob:
            return None
        cover_id = cover_blob[0]
        image_name = f"{cover_id}-{size}.jpg"
        return f"{self.covers_url}/b/id/{image_name}"

    def parse_search_data(
        self, data: JsonDict, min_confidence: float
    ) -> Iterator[SearchResult]:
        for idx, search_result in enumerate(data.get("docs", [])):
            # build the remote id from the openlibrary key
            key = self.books_url + search_result["key"]
            author = search_result.get("author_name") or ["Unknown"]
            cover_blob = search_result.get("cover_i")
            cover = self.get_cover_url([cover_blob], size="M") if cover_blob else None

            # OL doesn't provide confidence, but it does sort by an internal ranking, so
            # this confidence value is relative to the list position
            confidence = 1 / (idx + 1)

            yield SearchResult(
                title=search_result.get("title"),
                key=key,
                author=", ".join(author),
                connector=self,
                year=search_result.get("first_publish_year"),
                cover=cover,
                confidence=confidence,
            )

    def parse_isbn_search_data(self, data: JsonDict) -> Iterator[SearchResult]:
        for search_result in list(data.values()):
            # build the remote id from the openlibrary key
            key = self.books_url + search_result["key"]
            authors = search_result.get("authors") or [{"name": "Unknown"}]
            author_names = [author.get("name") for author in authors]
            cover_obj = search_result.get("cover")
            cover = cover_obj.get("medium") if cover_obj else ""
            yield SearchResult(
                title=search_result.get("title"),
                key=key,
                author=", ".join(author_names),
                connector=self,
                cover=cover,
                year=search_result.get("publish_date"),
            )

    def load_edition_data(self, olkey: str) -> JsonDict:
        """query openlibrary for editions of a work"""
        url = f"{self.books_url}/works/{olkey}/editions"
        return self.get_book_data(url)

    def expand_book_data(self, book: models.Book) -> None:
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

        for edition_data in edition_options.get("entries", []):
            # does this edition have ANY interesting data?
            if ignore_edition(edition_data):
                continue
            create_edition_task.delay(self.connector.id, work.id, edition_data)


def ignore_edition(edition_data: JsonDict) -> bool:
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


def get_description(description_blob: Union[JsonDict, str]) -> str:
    """descriptions can be a string or a dict"""
    if isinstance(description_blob, dict):
        description = markdown(description_blob.get("value", ""))
    else:
        description = markdown(description_blob)

    if (
        description.startswith("<p>")
        and description.endswith("</p>")
        and description.count("<p>") == 1
    ):
        # If there is just one <p> tag and it is around the text remove it
        return description[len("<p>") : -len("</p>")].strip()

    return clean(description)


def get_openlibrary_key(key: str) -> str:
    """convert /books/OL27320736M into OL27320736M"""
    return key.split("/")[-1]


def get_languages(language_blob: Iterable[JsonDict]) -> list[Optional[str]]:
    """/language/eng -> English"""
    langs = []
    for lang in language_blob:
        langs.append(languages.get(lang.get("key", ""), None))
    return langs


def get_dict_field(blob: Optional[JsonDict], field_name: str) -> Optional[Any]:
    """extract the isni from the remote id data for the author"""
    if not blob or not isinstance(blob, dict):
        return None
    return blob.get(field_name)


def get_wikipedia_link(links: list[Any]) -> Optional[str]:
    """extract wikipedia links"""
    if not isinstance(links, list):
        return None

    for link in links:
        if not isinstance(link, dict):
            continue
        if link.get("title") == "wikipedia":
            return link.get("url")
    return None


def get_inventaire_id(links: list[Any]) -> Optional[str]:
    """extract and format inventaire ids"""
    if not isinstance(links, list):
        return None

    for link in links:
        if not isinstance(link, dict):
            continue
        if link.get("title") == "inventaire.io":
            iv_link = link.get("url")
            if not isinstance(iv_link, str):
                return None
            return iv_link.split("/")[-1]
    return None


def pick_default_edition(options: list[JsonDict]) -> Optional[JsonDict]:
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


def parse_series(data: list[str]) -> str | None:
    """try to parse series name from different styles,
    * 'series name, #1'
    * 'title -- number'
    * 'title, Book number'
    * 'title (number)'
    """
    if not data:
        return None
    series_title = data[0].strip()
    for regex_to_try in [
        r"(.+)(?:, ?#\d+)$",
        r"(.+)(?:-- ?\d+)$",
        r"(.+)(?:, Book ?\d+)$",
        r"(.+)(?: \(\d+\))$",
    ]:
        if series_match := re.search(regex_to_try, series_title):
            series_name = series_match.group(1).strip()
            return series_name
    return series_title


def parse_series_number(data: list[str]) -> str | None:
    """try to parse series number from different styles,
    * 'series name, #1'
    * 'title -- number'
    * 'title, Book number'
    * 'title (number)'
    """
    if not data:
        return None
    series_title = data[0].strip()
    for regex_to_try in [
        r"(.+)#(\d+)$",
        r"(.+) -- (\d+)$",
        r"(.+), Book (\d+)$",
        r"(.+)\((\d+)\)",
    ]:
        if series_match := re.search(regex_to_try, series_title):
            series_number = series_match.group(2)
            return series_number
    return None
