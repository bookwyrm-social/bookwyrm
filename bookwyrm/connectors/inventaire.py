""" inventaire data connector """
import re
from typing import Any, Union, Optional, Iterator, Iterable

from bookwyrm import models
from bookwyrm.book_search import SearchResult
from .abstract_connector import AbstractConnector, Mapping, JsonDict
from .abstract_connector import get_data
from .connector_manager import ConnectorException, create_edition_task


class Connector(AbstractConnector):
    """instantiate a connector for inventaire"""

    generated_remote_link_field = "inventaire_id"

    def __init__(self, identifier: str):
        super().__init__(identifier)

        get_first = lambda a: a[0]
        shared_mappings = [
            Mapping("id", remote_field="uri", formatter=self.get_remote_id),
            Mapping("bnfId", remote_field="wdt:P268", formatter=get_first),
            Mapping("openlibraryKey", remote_field="wdt:P648", formatter=get_first),
        ]
        self.book_mappings = [
            Mapping("title", remote_field="wdt:P1476", formatter=get_first),
            Mapping("title", remote_field="labels", formatter=get_language_code),
            Mapping("subtitle", remote_field="wdt:P1680", formatter=get_first),
            Mapping("inventaireId", remote_field="uri"),
            Mapping(
                "description", remote_field="sitelinks", formatter=self.get_description
            ),
            Mapping("cover", remote_field="image", formatter=self.get_cover_url),
            Mapping("isbn13", remote_field="wdt:P212", formatter=get_first),
            Mapping("isbn10", remote_field="wdt:P957", formatter=get_first),
            Mapping("oclcNumber", remote_field="wdt:P5331", formatter=get_first),
            Mapping("goodreadsKey", remote_field="wdt:P2969", formatter=get_first),
            Mapping("librarythingKey", remote_field="wdt:P1085", formatter=get_first),
            Mapping("languages", remote_field="wdt:P407", formatter=self.resolve_keys),
            Mapping("publishers", remote_field="wdt:P123", formatter=self.resolve_keys),
            Mapping("publishedDate", remote_field="wdt:P577", formatter=get_first),
            Mapping("pages", remote_field="wdt:P1104", formatter=get_first),
            Mapping(
                "subjectPlaces", remote_field="wdt:P840", formatter=self.resolve_keys
            ),
            Mapping("subjects", remote_field="wdt:P921", formatter=self.resolve_keys),
            Mapping("asin", remote_field="wdt:P5749", formatter=get_first),
        ] + shared_mappings
        # TODO: P136: genre, P674 characters, P950 bne

        self.author_mappings = [
            Mapping("id", remote_field="uri", formatter=self.get_remote_id),
            Mapping("name", remote_field="labels", formatter=get_language_code),
            Mapping("bio", remote_field="sitelinks", formatter=self.get_description),
            Mapping("goodreadsKey", remote_field="wdt:P2963", formatter=get_first),
            Mapping("isni", remote_field="wdt:P213", formatter=get_first),
            Mapping("viafId", remote_field="wdt:P214", formatter=get_first),
            Mapping("gutenberg_id", remote_field="wdt:P1938", formatter=get_first),
            Mapping("born", remote_field="wdt:P569", formatter=get_first),
            Mapping("died", remote_field="wdt:P570", formatter=get_first),
        ] + shared_mappings

    def get_remote_id(self, value: str) -> str:
        """convert an id/uri into a url"""
        return f"{self.books_url}?action=by-uris&uris={value}"

    def get_book_data(self, remote_id: str) -> JsonDict:
        data = get_data(remote_id)
        extracted = list(data.get("entities", {}).values())
        try:
            data = extracted[0]
        except (KeyError, IndexError):
            raise ConnectorException("Invalid book data")
        # flatten the data so that images, uri, and claims are on the same level
        return {
            **data.get("claims", {}),
            **{
                k: data.get(k)
                for k in ["uri", "image", "labels", "sitelinks", "type"]
                if k in data
            },
        }

    def parse_search_data(
        self, data: JsonDict, min_confidence: float
    ) -> Iterator[SearchResult]:
        for search_result in data.get("results", []):
            images = search_result.get("image")
            cover = f"{self.covers_url}/img/entities/{images[0]}" if images else None
            # a deeply messy translation of inventaire's scores
            confidence = float(search_result.get("_score", 0.1))
            confidence = 0.1 if confidence < 150 else 0.999
            if confidence < min_confidence:
                continue
            yield SearchResult(
                title=search_result.get("label"),
                key=self.get_remote_id(search_result.get("uri")),
                author=search_result.get("description"),
                view_link=f"{self.base_url}/entity/{search_result.get('uri')}",
                cover=cover,
                confidence=confidence,
                connector=self,
            )

    def parse_isbn_search_data(self, data: JsonDict) -> Iterator[SearchResult]:
        """got some data"""
        results = data.get("entities")
        if not results:
            return
        for search_result in list(results.values()):
            title = search_result.get("claims", {}).get("wdt:P1476", [])
            if not title:
                continue
            yield SearchResult(
                title=title[0],
                key=self.get_remote_id(search_result.get("uri")),
                author=search_result.get("description"),
                view_link=f"{self.base_url}/entity/{search_result.get('uri')}",
                cover=self.get_cover_url(search_result.get("image")),
                connector=self,
            )

    def is_work_data(self, data: JsonDict) -> bool:
        return data.get("type") == "work"

    def load_edition_data(self, work_uri: str) -> JsonDict:
        """get a list of editions for a work"""
        # pylint: disable=line-too-long
        url = f"{self.books_url}?action=reverse-claims&property=wdt:P629&value={work_uri}&sort=true"
        return get_data(url)

    def get_edition_from_work_data(self, data: JsonDict) -> JsonDict:
        work_uri = data.get("uri")
        if not work_uri:
            raise ConnectorException("Invalid URI")
        data = self.load_edition_data(work_uri)
        try:
            uri = data.get("uris", [])[0]
        except IndexError:
            raise ConnectorException("Invalid book data")
        return self.get_book_data(self.get_remote_id(uri))

    def get_work_from_edition_data(self, data: JsonDict) -> JsonDict:
        try:
            uri = data.get("wdt:P629", [])[0]
        except IndexError:
            raise ConnectorException("Invalid book data")

        if not uri:
            raise ConnectorException("Invalid book data")
        return self.get_book_data(self.get_remote_id(uri))

    def get_authors_from_data(self, data: JsonDict) -> Iterator[models.Author]:
        authors = data.get("wdt:P50", [])
        for author in authors:
            model = self.get_or_create_author(self.get_remote_id(author))
            if model:
                yield model

    def expand_book_data(self, book: models.Book) -> None:
        work = book
        # go from the edition to the work, if necessary
        if isinstance(book, models.Edition):
            work = book.parent_work

        try:
            edition_options = self.load_edition_data(work.inventaire_id)
        except ConnectorException:
            # who knows, man
            return

        for edition_uri in edition_options.get("uris", []):
            remote_id = self.get_remote_id(edition_uri)
            create_edition_task.delay(self.connector.id, work.id, remote_id)

    def create_edition_from_data(
        self,
        work: models.Work,
        edition_data: Union[str, JsonDict],
        instance: Optional[models.Edition] = None,
    ) -> Optional[models.Edition]:
        """pass in the url as data and then call the version in abstract connector"""
        if isinstance(edition_data, str):
            try:
                edition_data = self.get_book_data(edition_data)
            except ConnectorException:
                # who, indeed, knows
                return None
        return super().create_edition_from_data(work, edition_data, instance=instance)

    def get_cover_url(
        self, cover_blob: Union[list[JsonDict], JsonDict], *_: Any
    ) -> Optional[str]:
        """format the relative cover url into an absolute one:
        {"url": "/img/entities/e794783f01b9d4f897a1ea9820b96e00d346994f"}
        """
        # covers may or may not be a list
        if isinstance(cover_blob, list):
            if len(cover_blob) == 0:
                return None
            cover_blob = cover_blob[0]
        cover_id = cover_blob.get("url")
        if not isinstance(cover_id, str):
            return None
        # cover may or may not be an absolute url already
        if re.match(r"^http", cover_id):
            return cover_id
        return f"{self.covers_url}{cover_id}"

    def resolve_keys(self, keys: Iterable[str]) -> list[str]:
        """cool, it's "wd:Q3156592" now what the heck does that mean"""
        results = []
        for uri in keys:
            try:
                data = self.get_book_data(self.get_remote_id(uri))
            except ConnectorException:
                continue
            results.append(get_language_code(data.get("labels", {})))
        return results

    def get_description(self, links: JsonDict) -> str:
        """grab an extracted excerpt from wikipedia"""
        link = links.get("enwiki")
        if not link:
            return ""
        url = f"{self.base_url}/api/data?action=wp-extract&lang=en&title={link}"
        try:
            data = get_data(url)
        except ConnectorException:
            return ""
        return data.get("extract", "")

    def get_remote_id_from_model(self, obj: models.BookDataModel) -> str:
        """use get_remote_id to figure out the link from a model obj"""
        remote_id_value = obj.inventaire_id
        return self.get_remote_id(remote_id_value)


def get_language_code(options: JsonDict, code: str = "en") -> Any:
    """when there are a bunch of translation but we need a single field"""
    result = options.get(code)
    if result:
        return result
    values = list(options.values())
    return values[0] if values else None
