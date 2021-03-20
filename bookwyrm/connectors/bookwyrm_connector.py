""" using another bookwyrm instance as a source of book data """
from bookwyrm import activitypub, models
from .abstract_connector import AbstractMinimalConnector, SearchResult


class Connector(AbstractMinimalConnector):
    """ this is basically just for search """

    def get_or_create_book(self, remote_id):
        edition = activitypub.resolve_remote_id(remote_id, model=models.Edition)
        work = edition.parent_work
        work.default_edition = work.get_default_edition()
        work.save()
        return edition

    def parse_search_data(self, data):
        return data

    def format_search_result(self, search_result):
        search_result["connector"] = self
        return SearchResult(**search_result)

    def parse_isbn_search_data(self, data):
        return data

    def format_isbn_search_result(self, search_result):
        return self.format_search_result(search_result)
