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
                   SearchVector('asin', weight='B') +\
                   SearchVector('oclc_number', weight='B') +\
                   SearchVector('remote_id', weight='B') +\
                   SearchVector('description', weight='C') +\
                   SearchVector('series', weight='C')
        ).filter(search=query)
        results = results.filter(default=True) or results

        search_results = []
        for book in results[:10]:
            search_results.append(
                self.format_search_result(book)
            )
        return search_results


    def format_search_result(self, book):
        return SearchResult(
            book.title,
            book.absolute_id,
            book.author_text,
            book.published_date.year if book.published_date else None,
        )


    def get_or_create_book(self, book_id):
        ''' since this is querying its own data source, it can only
        get a book, not load one from an external source '''
        try:
            return models.Book.objects.select_subclasses().get(
                id=book_id
            )
        except ObjectDoesNotExist:
            return None


    def is_work_data(self, data):
        pass

    def get_edition_from_work_data(self, data):
        pass

    def get_work_from_edition_date(self, data):
        pass

    def get_authors_from_data(self, data):
        return None

    def get_cover_from_data(self, data):
        return None

    def parse_search_data(self, data):
        ''' it's already in the right format, don't even worry about it '''
        return data

    def expand_book_data(self, book):
        pass
