''' using a fedireads instance as a source of book data '''
from django.core.exceptions import ObjectDoesNotExist

from fedireads import models
from .abstract_connector import AbstractConnector


class Connector(AbstractConnector):
    ''' instantiate a connector  '''
    def __init__(self, identifier):
        super().__init__(identifier)


    def search(self, query):
        ''' right now you can't search fedireads sorry, but when
        that gets implemented it will totally rule '''
        return []


    def get_or_create_book(self, fedireads_key):
        ''' since this is querying its own data source, it can only
        get a book, not load one from an external source '''
        try:
            return models.Book.objects.select_subclasses().get(
                fedireads_key=fedireads_key
            )
        except ObjectDoesNotExist:
            return None


    def get_or_create_author(self, fedireads_key):
        ''' load that author '''
        try:
            return models.Author.objects.get(fedreads_key=fedireads_key)
        except ObjectDoesNotExist:
            pass


    def update_book(self, book_obj):
        pass
