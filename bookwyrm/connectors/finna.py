"""finna data connector"""

import re
from typing import Iterator

from bookwyrm import models
from bookwyrm.book_search import SearchResult
from bookwyrm.models.book import FormatChoices
from .abstract_connector import AbstractConnector, Mapping, JsonDict
from .abstract_connector import get_data
from .connector_manager import ConnectorException, create_edition_task
from .openlibrary_languages import languages


class Connector(AbstractConnector):
    """instantiate a connector for finna"""

    generated_remote_link_field = "id"

    def __init__(self, identifier: str):
        super().__init__(identifier)

        get_first = lambda x, *args: x[0] if x else None
        format_remote_id = lambda x: f"{self.books_url}{x}"
        format_cover_url = lambda x: f"{self.covers_url}{x[0]}" if x else None
        self.book_mappings = [
            Mapping("id", remote_field="id", formatter=format_remote_id),
            Mapping("finnaKey", remote_field="id"),
            Mapping("title", remote_field="shortTitle"),
            Mapping("title", remote_field="title"),
            Mapping("subtitle", remote_field="subTitle"),
            Mapping("isbn10", remote_field="cleanIsbn"),
            Mapping("languages", remote_field="languages", formatter=resolve_languages),
            Mapping("authors", remote_field="authors", formatter=parse_authors),
            Mapping("subjects", formatter=join_subject_list),
            Mapping("publishedDate", remote_field="year"),
            Mapping("cover", remote_field="images", formatter=format_cover_url),
            Mapping("description", remote_field="summary", formatter=get_first),
            Mapping("series", remote_field="series", formatter=parse_series_name),
            Mapping(
                "seriesNumber",
                remote_field="series",
                formatter=parse_series_number,
            ),
            Mapping("publishers", remote_field="publishers"),
            Mapping(
                "physicalFormat",
                remote_field="formats",
                formatter=describe_physical_format,
            ),
            Mapping(
                "physicalFormatDetail",
                remote_field="physicalDescriptions",
                formatter=get_first,
            ),
            Mapping(
                "pages",
                remote_field="physicalDescriptions",
                formatter=guess_page_numbers,
            ),
        ]

        self.author_mappings = [
            Mapping("id", remote_field="authors", formatter=self.get_remote_author_id),
            Mapping("name", remote_field="authors", formatter=get_first_author),
        ]

    def get_book_data(self, remote_id: str) -> JsonDict:
        request_parameters = {
            "field[]": [
                "authors",
                "cleanIsbn",
                "formats",
                "id",
                "images",
                "isbns",
                "languages",
                "physicalDescriptions",
                "publishers",
                "recordPage",
                "series",
                "shortTitle",
                "subjects",
                "subTitle",
                "summary",
                "title",
                "year",
            ]
        }
        data = get_data(
            url=remote_id, params=request_parameters  # type:ignore[arg-type]
        )
        extracted = data.get("records", [])
        try:
            data = extracted[0]
        except (KeyError, IndexError):
            raise ConnectorException("Invalid book data")
        return data

    def get_remote_author_id(self, data: JsonDict) -> str | None:
        """return search url for author info, as we don't
        have way to retrieve author-id with the query"""
        author = get_first_author(data)
        if author:
            return f"{self.search_url}{author}&type=Author"
        return None

    def get_remote_id(self, data: JsonDict) -> str:
        """return record-id page as book-id"""
        return f"{self.books_url}{data.get('id')}"

    def parse_search_data(
        self, data: JsonDict, min_confidence: float
    ) -> Iterator[SearchResult]:
        for idx, search_result in enumerate(data.get("records", [])):
            authors = search_result.get("authors")
            author = None
            if authors:
                author_list = parse_authors(authors)
                if author_list:
                    author = "; ".join(author_list)

            confidence = 1 / (idx + 1)
            if confidence < min_confidence:
                break

            # Create some extra info on edition if it is audio-book or e-book
            edition_info_title = describe_physical_format(search_result.get("formats"))
            edition_info = ""
            if edition_info_title and edition_info_title != "Hardcover":
                for book_format, info_title in FormatChoices:
                    if book_format == edition_info_title:
                        edition_info = f" {info_title}"
                        break

            search_result = SearchResult(
                title=f"{search_result.get('title')}{edition_info}",
                key=f"{self.books_url}{search_result.get('id')}",
                author=author,
                cover=f"{self.covers_url}{search_result.get('images')[0]}"
                if search_result.get("images")
                else None,
                year=search_result.get("year"),
                view_link=f"{self.base_url}{search_result.get('recordPage')}",
                confidence=confidence,
                connector=self,
            )
            yield search_result

    def parse_isbn_search_data(self, data: JsonDict) -> Iterator[SearchResult]:
        """got some data"""
        for idx, search_result in enumerate(data.get("records", [])):
            authors = search_result.get("authors")
            author = None
            if authors:
                author_list = parse_authors(authors)
                if author_list:
                    author = "; ".join(author_list)

            confidence = 1 / (idx + 1)
            yield SearchResult(
                title=search_result.get("title"),
                key=f"{self.books_url}{search_result.get('id')}",
                author=author,
                cover=f"{self.covers_url}{search_result.get('images')[0]}"
                if search_result.get("images")
                else None,
                year=search_result.get("year"),
                view_link=f"{self.base_url}{search_result.get('recordPage')}",
                confidence=confidence,
                connector=self,
            )

    def get_authors_from_data(self, data: JsonDict) -> Iterator[models.Author]:
        authors = data.get("authors")
        if authors:
            for author in parse_authors(authors):
                model = self.get_or_create_author(
                    f"{self.search_url}{author}&type=Author"
                )
                if model:
                    yield model

    def expand_book_data(self, book: models.Book) -> None:
        work = book
        # go from the edition to the work, if necessary
        if isinstance(book, models.Edition):
            work = book.parent_work

        try:
            edition_options = retrieve_versions(work.finna_key)
        except ConnectorException:
            return

        for edition in edition_options:
            remote_id = self.get_remote_id(edition)
            if remote_id:
                create_edition_task.delay(self.connector.id, work.id, edition)

    def get_remote_id_from_model(self, obj: models.BookDataModel) -> str:
        """use get_remote_id to figure out the link from a model obj"""
        return f"{self.books_url}{obj.finna_key}"

    def is_work_data(self, data: JsonDict) -> bool:
        """
        https://api.finna.fi/v1/search?id=anders.1946700&search=versions&view=&lng=fi&field[]=formats&field[]=series&field[]=title&field[]=authors&field[]=summary&field[]=cleanIsbn&field[]=id

        No real ordering what is work and what is edition, so pick first version as work
        """
        edition_list = retrieve_versions(data.get("id"))
        if edition_list:
            return data.get("id") == edition_list[0].get("id")
        return True

    def get_edition_from_work_data(self, data: JsonDict) -> JsonDict:
        """No real distinctions what is work/edition,
        so check all versions and pick preferred edition"""
        edition_list = retrieve_versions(data.get("id"))
        if not edition_list:
            raise ConnectorException("No editions found for work")
        edition = pick_preferred_edition(edition_list)
        if not edition:
            raise ConnectorException("No editions found for work")
        return edition

    def get_work_from_edition_data(self, data: JsonDict) -> JsonDict:
        return retrieve_versions(data.get("id"))[0]


def guess_page_numbers(data: JsonDict) -> str | None:
    """Try to retrieve page count of edition"""
    for row in data:
        # Try to match page count text in style of '134 pages' or '134 sivua'
        page_search = re.search(r"(\d+) (sivua|s\.|sidor|pages)", row)
        page_count = page_search.group(1) if page_search else None
        if page_count:
            return page_count
        # If we didn't match, try starting number
        page_search = re.search(r"^(\d+)", row)
        page_count = page_search.group(1) if page_search else None
        if page_count:
            return page_count
    return None


def resolve_languages(data: JsonDict) -> list[str]:
    """Use openlibrary language code list to resolve iso-lang codes"""
    result_languages = []
    for language_code in data:
        result_languages.append(
            languages.get(f"/languages/{language_code}", language_code)
        )
    return result_languages


def join_subject_list(data: list[JsonDict]) -> list[str]:
    """Join list of string list about subject topics as one list"""
    return [" ".join(info) for info in data]


def describe_physical_format(formats: list[JsonDict]) -> str:
    """Map if book is physical book, eBook or audiobook"""
    found_format = "Hardcover"
    # Map finnish finna formats to bookwyrm codes
    format_mapping = {
        "1/Book/Book/": "Hardcover",
        "1/Book/AudioBook/": "AudiobookFormat",
        "1/Book/eBook/": "EBook",
    }
    for format_to_check in formats:
        format_value = format_to_check.get("value")
        if not isinstance(format_value, str):
            continue
        if (mapping_match := format_mapping.get(format_value, None)) is not None:
            found_format = mapping_match
    return found_format


def parse_series_name(series: list[JsonDict]) -> str | None:
    """Parse series name if given"""
    for info in series:
        if "name" in info:
            return info.get("name")
    return None


def parse_series_number(series: list[JsonDict]) -> str | None:
    """Parse series number from additional info if given"""
    for info in series:
        if "additional" in info:
            return info.get("additional")
    return None


def retrieve_versions(book_id: str | None) -> list[JsonDict]:
    """
    https://api.finna.fi/v1/search?id=anders.1946700&search=versions&view=&

    Search all editions/versions of the book that finna is aware of
    """

    if not book_id:
        return []

    request_parameters = {
        "id": book_id,
        "search": "versions",
        "view": "",
        "field[]": [
            "authors",
            "cleanIsbn",
            "edition",
            "formats",
            "id",
            "images",
            "isbns",
            "languages",
            "physicalDescriptions",
            "publishers",
            "recordPage",
            "series",
            "shortTitle",
            "subjects",
            "subTitle",
            "summary",
            "title",
            "year",
        ],
    }
    data = get_data(
        url="https://api.finna.fi/api/v1/search",
        params=request_parameters,  # type: ignore[arg-type]
    )
    result = data.get("records", [])
    if isinstance(result, list):
        return result
    return []


def get_first_author(data: JsonDict) -> str | None:
    """Parse authors and return first one, usually the main author"""
    authors = parse_authors(data)
    if authors:
        return authors[0]
    return None


def parse_authors(data: JsonDict) -> list[str]:
    """Search author info, they are given in SurName, FirstName style
    return them also as FirstName SurName order"""
    if author_keys := data.get("primary", None):
        if author_keys:
            # we search for 'kirjoittaja' role, if any found
            tulos = list(
                # Convert from 'Lewis, Michael' to 'Michael Lewis'
                " ".join(reversed(author_key.split(", ")))
                for author_key, author_info in author_keys.items()
                if "kirjoittaja" in author_info.get("role", [])
            )
            if tulos:
                return tulos
            # if not found, we search any role that is not specificly something
            tulos = list(
                " ".join(reversed(author_key.split(", ")))
                for author_key, author_info in author_keys.items()
                if "-" in author_info.get("role", [])
            )
            return tulos
    return []


def pick_preferred_edition(options: list[JsonDict]) -> JsonDict | None:
    """favor physical copies with covers in english"""
    if not options:
        return None
    if len(options) == 1:
        return options[0]

    # pick hardcodver book if present over eBook/audiobook
    formats = ["1/Book/Book/"]
    format_selection = []
    for edition in options:
        for edition_format in edition.get("formats", []):
            if edition_format.get("value") in formats:
                format_selection.append(edition)
    options = format_selection or options

    # Prefer Finnish/Swedish language editions if any found
    language_list = ["fin", "swe"]
    languages_selection = []
    for edition in options:
        for edition_language in edition.get("languages", []):
            if edition_language in language_list:
                languages_selection.append(edition)
    options = languages_selection or options

    options = [e for e in options if e.get("cleanIsbn")] or options
    return options[0]
