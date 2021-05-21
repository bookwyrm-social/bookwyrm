""" inventaire data connector """
import re

from bookwyrm import models
from .abstract_connector import AbstractConnector, SearchResult, Mapping
from .abstract_connector import get_data
from .connector_manager import ConnectorException


class Connector(AbstractConnector):
    """instantiate a connector for OL"""

    def __init__(self, identifier):
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

    def get_remote_id(self, value):
        """convert an id/uri into a url"""
        return "{:s}?action=by-uris&uris={:s}".format(self.books_url, value)

    def get_book_data(self, remote_id):
        data = get_data(remote_id)
        extracted = list(data.get("entities").values())
        try:
            data = extracted[0]
        except KeyError:
            raise ConnectorException("Invalid book data")
        # flatten the data so that images, uri, and claims are on the same level
        return {
            **data.get("claims", {}),
            **{k: data.get(k) for k in ["uri", "image", "labels", "sitelinks"]},
        }

    def search(self, query, min_confidence=None):
        """overrides default search function with confidence ranking"""
        results = super().search(query)
        if min_confidence:
            # filter the search results after the fact
            return [r for r in results if r.confidence >= min_confidence]
        return results

    def parse_search_data(self, data):
        return data.get("results")

    def format_search_result(self, search_result):
        images = search_result.get("image")
        cover = (
            "{:s}/img/entities/{:s}".format(self.covers_url, images[0])
            if images
            else None
        )
        # a deeply messy translation of inventaire's scores
        confidence = float(search_result.get("_score", 0.1))
        confidence = 0.1 if confidence < 150 else 0.999
        return SearchResult(
            title=search_result.get("label"),
            key=self.get_remote_id(search_result.get("uri")),
            author=search_result.get("description"),
            view_link="{:s}/entity/{:s}".format(
                self.base_url, search_result.get("uri")
            ),
            cover=cover,
            confidence=confidence,
            connector=self,
        )

    def parse_isbn_search_data(self, data):
        """got some daaaata"""
        results = data.get("entities")
        if not results:
            return []
        return list(results.values())

    def format_isbn_search_result(self, search_result):
        """totally different format than a regular search result"""
        title = search_result.get("claims", {}).get("wdt:P1476", [])
        if not title:
            return None
        return SearchResult(
            title=title[0],
            key=self.get_remote_id(search_result.get("uri")),
            author=search_result.get("description"),
            view_link="{:s}/entity/{:s}".format(
                self.base_url, search_result.get("uri")
            ),
            cover=self.get_cover_url(search_result.get("image")),
            connector=self,
        )

    def is_work_data(self, data):
        return data.get("type") == "work"

    def load_edition_data(self, work_uri):
        """get a list of editions for a work"""
        url = (
            "{:s}?action=reverse-claims&property=wdt:P629&value={:s}&sort=true".format(
                self.books_url, work_uri
            )
        )
        return get_data(url)

    def get_edition_from_work_data(self, data):
        data = self.load_edition_data(data.get("uri"))
        try:
            uri = data["uris"][0]
        except KeyError:
            raise ConnectorException("Invalid book data")
        return self.get_book_data(self.get_remote_id(uri))

    def get_work_from_edition_data(self, data):
        uri = data.get("wdt:P629", [None])[0]
        if not uri:
            raise ConnectorException("Invalid book data")
        return self.get_book_data(self.get_remote_id(uri))

    def get_authors_from_data(self, data):
        authors = data.get("wdt:P50", [])
        for author in authors:
            yield self.get_or_create_author(self.get_remote_id(author))

    def expand_book_data(self, book):
        work = book
        # go from the edition to the work, if necessary
        if isinstance(book, models.Edition):
            work = book.parent_work

        try:
            edition_options = self.load_edition_data(work.inventaire_id)
        except ConnectorException:
            # who knows, man
            return

        for edition_uri in edition_options.get("uris"):
            remote_id = self.get_remote_id(edition_uri)
            try:
                data = self.get_book_data(remote_id)
            except ConnectorException:
                # who, indeed, knows
                continue
            self.create_edition_from_data(work, data)

    def get_cover_url(self, cover_blob, *_):
        """format the relative cover url into an absolute one:
        {"url": "/img/entities/e794783f01b9d4f897a1ea9820b96e00d346994f"}
        """
        # covers may or may not be a list
        if isinstance(cover_blob, list) and len(cover_blob) > 0:
            cover_blob = cover_blob[0]
        cover_id = cover_blob.get("url")
        if not cover_id:
            return None
        # cover may or may not be an absolute url already
        if re.match(r"^http", cover_id):
            return cover_id
        return "%s%s" % (self.covers_url, cover_id)

    def resolve_keys(self, keys):
        """cool, it's "wd:Q3156592" now what the heck does that mean"""
        results = []
        for uri in keys:
            try:
                data = self.get_book_data(self.get_remote_id(uri))
            except ConnectorException:
                continue
            results.append(get_language_code(data.get("labels")))
        return results

    def get_description(self, links):
        """grab an extracted excerpt from wikipedia"""
        link = links.get("enwiki")
        if not link:
            return ""
        url = "{:s}/api/data?action=wp-extract&lang=en&title={:s}".format(
            self.base_url, link
        )
        try:
            data = get_data(url)
        except ConnectorException:
            return ""
        return data.get("extract")


def get_language_code(options, code="en"):
    """when there are a bunch of translation but we need a single field"""
    result = options.get(code)
    if result:
        return result
    values = list(options.values())
    return values[0] if values else None
