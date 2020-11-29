''' using another bookwyrm instance as a source of book data '''
from bookwyrm import activitypub, models
from .abstract_connector import AbstractMinimalConnector, SearchResult


class Connector(AbstractMinimalConnector):
    ''' this is basically just for search '''

    def get_or_create_book(self, remote_id):
        return activitypub.resolve_remote_id(models.Edition, remote_id)

    def parse_search_data(self, data):
        return data

    def format_search_result(self, search_result):
        return SearchResult(**search_result)
