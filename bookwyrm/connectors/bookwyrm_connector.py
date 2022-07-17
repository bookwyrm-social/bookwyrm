""" using another bookwyrm instance as a source of book data """
from bookwyrm import activitypub, models
from bookwyrm.book_search import SearchResult
from .abstract_connector import AbstractMinimalConnector


class Connector(AbstractMinimalConnector):
    """this is basically just for search"""

    def get_or_create_book(self, remote_id):
        return activitypub.resolve_remote_id(remote_id, model=models.Edition)

    def parse_search_data(self, data, min_confidence):
        for search_result in data:
            search_result["connector"] = self
            yield SearchResult(**search_result)

    def parse_isbn_search_data(self, data):
        for search_result in data:
            search_result["connector"] = self
            yield SearchResult(**search_result)
