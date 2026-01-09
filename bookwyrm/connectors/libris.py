"""Libris (Swedish National Library) data connector"""

import re
from typing import Iterator

from bookwyrm import models
from bookwyrm.book_search import SearchResult

from .abstract_connector import AbstractConnector, JsonDict, Mapping, get_data
from .connector_manager import ConnectorException
from .openlibrary_languages import languages


def get_first(value):
    """Extract first element if value is a list, otherwise return as-is."""
    if isinstance(value, list):
        return value[0] if value else None
    return value


def join_paragraphs(value: str | list | None) -> str | None:
    """join list elements with newlines, or return string as-is."""
    if not value:
        return None
    return value if isinstance(value, str) else "\n".join(value)


def extract_id_from_url(url: str | None) -> str | None:
    """extract the Libris ID from a URL like http://libris.kb.se/bib/6rkftbcz44gf3pqm"""
    if not url:
        return None
    match = re.search(r"libris\.kb\.se/bib/([a-zA-Z0-9]+)", url)
    if match:
        return match.group(1)
    return None


def resolve_languages(data: str | list | None) -> list[str]:
    """Convert ISO language codes to language names using OpenLibrary language map"""
    if not data:
        return []

    if isinstance(data, str):
        data = [data]

    result = []
    for lang_code in data:
        # try to find in OpenLibrary languages
        lang_name = languages.get(f"/languages/{lang_code}", lang_code)
        result.append(lang_name)
    return result


def parse_isbn(isbn: str | list | None, length: int) -> str | None:
    """extract ISBN of specified length from ISBN field.

    args:
        isbn: Raw ISBN value (string or list)
        length: Expected ISBN length (10 or 13)

    """
    if not isbn:
        return None

    # only allow 'X' for ISBN-10
    pattern = r"[^0-9X]" if length == 10 else r"[^0-9]"

    if isinstance(isbn, list):
        for i in isbn:
            cleaned = re.sub(pattern, "", str(i).upper())
            if len(cleaned) == length:
                return cleaned
        return None

    cleaned = re.sub(pattern, "", str(isbn).upper())
    return cleaned if len(cleaned) == length else None


def parse_isbn13(isbn: str | list | None) -> str | None:
    """extract ISBN-13 from ISBN field"""
    return parse_isbn(isbn, 13)


def parse_isbn10(isbn: str | list | None) -> str | None:
    """extract ISBN-10 from ISBN field"""
    return parse_isbn(isbn, 10)


def parse_publishers(publisher: str | list | None) -> list[str]:
    """parse publisher field, handling 'City : Publisher' format"""
    if not publisher:
        return []

    if isinstance(publisher, str):
        publisher = [publisher]

    result = []
    for pub in publisher:
        if " : " in pub:
            result.append(pub.split(" : ", 1)[1].strip())
        else:
            result.append(pub.strip())
    return result


def parse_author_name(author: str | None) -> str | None:
    """
    parse a single author from Libris format.
    format is typically: "Lastname, Firstname, year-" or "Lastname, Firstname"
    sometimes includes trailing dot: "Lastname, Firstname, year- ."
    returns: "Firstname Lastname" or None
    """
    if not author:
        return None

    # remove year information (e.g., "1976-", "1900-1980", or "1947- .")
    author = re.sub(r",?\s*\d{4}-?\d*\s*\.?\s*$", "", author).strip()

    # handle "Lastname, Firstname" format
    if ", " in author:
        parts = author.split(", ", 1)
        if len(parts) == 2:
            return f"{parts[1]} {parts[0]}"

    return author


def parse_authors(creator: str | list | None) -> list[str]:
    """parse creator field into list of author names.

    deduplicates authors since the API sometimes returns the same author
    multiple times (e.g. with/without trailing dots).
    """
    if not creator:
        return []

    if isinstance(creator, str):
        creator = [creator]

    result = []
    for author in creator:
        name = parse_author_name(author)
        if name:
            result.append(name)

    # deduplicate while preserving order
    return list(dict.fromkeys(result))


def get_first_author_name(data: str | list | None) -> str | None:
    """get the first author's name from creator data"""
    authors = parse_authors(data)
    return authors[0] if authors else None


def format_authors_for_display(creator: str | list | None) -> str | None:
    """format authors for display in search results (semicolon-separated)"""
    authors = parse_authors(creator)
    if not authors:
        return None
    if len(authors) == 1:
        return authors[0]
    return "; ".join(authors)


class Connector(AbstractConnector):
    """instantiate a connector for Libris"""

    generated_remote_link_field = "identifier"

    def __init__(self, identifier: str):
        super().__init__(identifier)

        self.book_mappings = [
            Mapping("id", remote_field="identifier"),
            Mapping(
                "librisKey", remote_field="identifier", formatter=extract_id_from_url
            ),
            Mapping("title", remote_field="title", formatter=get_first),
            Mapping("isbn13", remote_field="isbn", formatter=parse_isbn13),
            Mapping("isbn10", remote_field="isbn", formatter=parse_isbn10),
            Mapping("languages", remote_field="language", formatter=resolve_languages),
            Mapping("authors", remote_field="creator", formatter=parse_authors),
            Mapping("publishedDate", remote_field="date", formatter=get_first),
            Mapping("publishers", remote_field="publisher", formatter=parse_publishers),
            Mapping(
                "description", remote_field="description", formatter=join_paragraphs
            ),
        ]

        self.author_mappings = [
            Mapping("id", remote_field="creator", formatter=self.get_remote_author_id),
            Mapping("name", remote_field="creator", formatter=get_first_author_name),
        ]

    def get_book_data(self, remote_id: str) -> JsonDict:
        """fetch book data from Libris using the identifier URL"""
        libris_id = extract_id_from_url(remote_id)
        if not libris_id:
            raise ConnectorException(f"Invalid Libris ID: {remote_id}")

        # query using just the libris bib ID (no prefix needed)
        query_url = f"{self.search_url}{libris_id}"
        data = get_data(url=query_url)

        xsearch = data.get("xsearch", {})
        records = xsearch.get("list", [])

        if not records:
            raise ConnectorException(f"No book found for ID: {libris_id}")
        return records[0]

    def get_remote_author_id(self, data: JsonDict) -> str | None:
        """return search URL for author info"""
        author = get_first_author_name(data)
        if author:
            return f"{self.search_url}forf:({author})"
        return None

    def get_remote_id(self, data: JsonDict) -> str:
        """return the identifier URL as the book ID"""
        identifier = get_first(data.get("identifier"))
        return identifier or ""

    def _parse_records(
        self, data: JsonDict, min_confidence: float | None = None
    ) -> Iterator[SearchResult]:
        """Parse search results from Libris Xsearch API.

        Args:
            data: Raw API response data
            min_confidence: If provided, stop yielding results below this threshold
        """
        xsearch = data.get("xsearch", {})
        records = xsearch.get("list", [])

        for idx, record in enumerate(records):
            confidence = 1 / (idx + 1)
            if min_confidence is not None and confidence < min_confidence:
                break

            yield SearchResult(
                title=get_first(record.get("title")),
                key=get_first(record.get("identifier")),
                author=format_authors_for_display(record.get("creator")),
                cover=None,  # Libris doesn't provide cover images in JSON
                year=get_first(record.get("date")),
                view_link=get_first(record.get("identifier")),
                confidence=confidence,
                connector=self,
            )

    def parse_search_data(
        self, data: JsonDict, min_confidence: float
    ) -> Iterator[SearchResult]:
        """parse search results from Libris Xsearch API"""
        return self._parse_records(data, min_confidence)

    def parse_isbn_search_data(self, data: JsonDict) -> Iterator[SearchResult]:
        """parse ISBN search results"""
        return self._parse_records(data)

    def get_authors_from_data(self, data: JsonDict) -> Iterator[models.Author]:
        """extract author information from book data.

        Libris doesn't have a dedicated author endpoint, so we create authors
        directly from the book data rather than fetching from a remote URL.

        WARNING: This matches authors by name only, which will incorrectly link
        different people with the same name.
        """
        creator = data.get("creator")
        authors = parse_authors(creator)

        for author_name in authors:
            existing = models.Author.objects.filter(name=author_name).first()
            if existing:
                yield existing
                continue

            author = models.Author.objects.create(name=author_name)
            yield author

    def expand_book_data(self, book: models.Book) -> None:
        """Libris doesn't have a versions/editions endpoint"""
        pass

    def get_remote_id_from_model(self, obj: models.BookDataModel) -> str:
        """use libris_key to construct the remote URL"""
        if obj.libris_key:
            return f"https://libris.kb.se/bib/{obj.libris_key}"
        return ""

    def is_work_data(self, data: JsonDict) -> bool:
        """Libris doesn't distinguish between works and editions"""
        return True

    def get_edition_from_work_data(self, data: JsonDict) -> JsonDict:
        """return the same data as the edition"""
        return data

    def get_work_from_edition_data(self, data: JsonDict) -> JsonDict:
        """return the same data as the work"""
        return data
