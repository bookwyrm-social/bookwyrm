""" inventaire data connector """
from .abstract_connector import AbstractConnector, SearchResult, Mapping
from .abstract_connector import get_data


class Connector(AbstractConnector):
    """ instantiate a connector for OL """

    def __init__(self, identifier):
        super().__init__(identifier)

        get_remote_id = lambda a, *args: self.books_url + a
        get_remote_id_list = lambda a, *_: [get_remote_id(v) for v in a]
        self.book_mappings = [
            Mapping("title", remote_field="wdt:P1476", formatter=get_claim),
            Mapping("subtitle", remote_field="wdt:P1680", formatter=get_claim),
            Mapping("id", remote_field="uri", formatter=get_remote_id),
            Mapping("authors", remote_field="wdt:P50", formatter=get_remote_id_list),
            Mapping("inventaireId", remote_field="uri"),
            Mapping("cover", remote_field="image", formatter=self.get_cover_url),
            Mapping("isbn13", remote_field="wdt:P212", formatter=get_claim),
            Mapping("isbn10", remote_field="wdt:P957", formatter=get_claim),
            Mapping("languages", remote_field="wdt:P407", formatter=get_language),
            Mapping("publishers", remote_field="wdt:P123", formatter=resolve_key),
            Mapping("publishedDate", remote_field="wdt:P577", formatter=get_claim),
            Mapping("pages", remote_field="wdt:P1104", formatter=get_claim),
            Mapping("goodreadsKey", remote_field="wdt:P2969", formatter=get_claim),
            Mapping("openlibraryKey", remote_field="wdt:P648", formatter=get_claim),
            Mapping("subjectPlaces", remote_field="wdt:P840", formatter=resolve_key),
            Mapping("subjects", remote_field="wdt:P921", formatter=resolve_key),
            Mapping("librarythingKey", remote_field="wdt:P1085", formatter=get_claim),
            Mapping("oclcNumber", remote_field="wdt:P5331", formatter=get_claim),
            Mapping("asin", remote_field="wdt:P5749", formatter=get_claim),
        ]
        # TODO: P136: genre, P268 bnf id, P674 characters, P950 bne

    def get_book_data(self, remote_id):
        data = get_data(remote_id)
        extracted = list(data.get("entities").values())
        return extracted[0] if extracted else {}

    def parse_search_data(self, data):
        return data.get('results')

    def format_search_result(self, search_result):
        images = search_result.get("image")
        cover = "{:s}/img/entities/{:s}".format(
            self.covers_url, images[0]
        ) if images else None
        return SearchResult(
            title=search_result.get("label"),
            key="{:s}{:s}".format(self.books_url, search_result.get("uri")),
            view_link="{:s}{:s}".format(self.base_url, search_result.get("uri")),
            cover=cover,
            connector=self,
        )

    def parse_isbn_search_data(self, data):
        """ boop doop """

    def format_isbn_search_result(self, search_result):
        """ beep bloop """

    def is_work_data(self, data):
        return data.get("type") == "work"

    def get_edition_from_work_data(self, data):
        return {}

    def get_work_from_edition_data(self, data):
        # P629
        return {}

    def get_authors_from_data(self, data):
        return []

    def expand_book_data(self, book):
        return

    def get_cover_url(self, cover_blob, *_):
        """ format the relative cover url into an absolute one:
        {"url": "/img/entities/e794783f01b9d4f897a1ea9820b96e00d346994f"}
        """
        cover_id = cover_blob[0].get("url")
        if not cover_id:
            return None
        return "%s%s" % (self.covers_url, cover_id)


def get_claim(data, claim_key):
    """ all the metadata is in a "claims" dict with a buncha wikidata keys """
    return data.get('claims', {}).get(claim_key)

def get_language(wikidata_key, *_):
    """ who here speaks "wd:Q150" """
    return wikidata_key  # TODO

def resolve_key(wikidata_key, *_):
    """ cool, it's "wd:Q3156592" now what the heck does that mean """
    return wikidata_key  # TODO
