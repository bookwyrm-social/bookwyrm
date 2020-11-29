''' using another bookwyrm instance as a source of book data '''
from bookwyrm import activitypub, models
from .abstract_connector import AbstractConnector, SearchResult


class Connector(AbstractConnector):
    ''' this is basically just for search '''

    def get_or_create_book(self, remote_id):
        return activitypub.resolve_remote_id(models.Edition, remote_id)

    def parse_search_data(self, data):
        return data

    def format_search_result(self, search_result):
        return SearchResult(**search_result)

    def get_remote_id_from_data(self, data):
        pass

    def is_work_data(self, data):
        pass

    def get_edition_from_work_data(self, data):
        pass

    def get_work_from_edition_date(self, data):
        pass

    def get_cover_from_data(self, data):
        pass

    def expand_book_data(self, book):
        pass

    def get_authors_from_data(self, data):
        pass
