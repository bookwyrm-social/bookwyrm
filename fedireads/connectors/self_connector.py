''' using a fedireads instance as a source of book data '''
from django.contrib.postgres.search import SearchVector
from django.core.exceptions import ObjectDoesNotExist

from fedireads import models
from .abstract_connector import AbstractConnector, SearchResult


class Connector(AbstractConnector):
    ''' instantiate a connector  '''
    def __init__(self, identifier):
        super().__init__(identifier)


    def search(self, query):
        ''' right now you can't search fedireads sorry, but when
        that gets implemented it will totally rule '''
        results = models.Edition.objects.annotate(
            search=SearchVector('title', weight='A') +\
                   SearchVector('subtitle', weight='B') +\
                   SearchVector('author_text', weight='A') +\
                   SearchVector('isbn_13', weight='A') +\
                   SearchVector('isbn_10', weight='A') +\
                   SearchVector('openlibrary_key', weight='B') +\
                   SearchVector('goodreads_key', weight='B') +\
                   SearchVector('source_url', weight='B') +\
                   SearchVector('asin', weight='B') +\
                   SearchVector('oclc_number', weight='B') +\
                   SearchVector('description', weight='C') +\
                   SearchVector('series', weight='C')
        ).filter(search=query)
        results = results.filter(default=True) or results

        search_results = []
        for book in results[:10]:
            search_results.append(
                SearchResult(
                    book.title,
                    book.fedireads_key,
                    book.author_text,
                    book.published_date.year if book.published_date else None,
                    None
                )
            )
        return search_results


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


    def expand_book_data(self, book):
        pass
