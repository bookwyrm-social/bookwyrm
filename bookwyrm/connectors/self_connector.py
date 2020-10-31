''' using a bookwyrm instance as a source of book data '''
from django.contrib.postgres.search import SearchRank, SearchVector

from bookwyrm import models
from .abstract_connector import AbstractConnector, SearchResult


class Connector(AbstractConnector):
    ''' instantiate a connector  '''
    def search(self, query, min_confidence=0.1):
        ''' right now you can't search bookwyrm sorry, but when
        that gets implemented it will totally rule '''
        vector = SearchVector('title', weight='A') +\
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

        results = models.Edition.objects.annotate(
            search=vector
        ).annotate(
            rank=SearchRank(vector, query)
        ).filter(
            rank__gt=min_confidence
        ).order_by('-rank')
        results = results.filter(default=True) or results

        search_results = []
        for book in results[:10]:
            search_results.append(
                self.format_search_result(book)
            )
        return search_results


    def format_search_result(self, search_result):
        return SearchResult(
            title=search_result.title,
            key=search_result.local_id,
            author=search_result.author_text,
            year=search_result.published_date.year if \
                    search_result.published_date else None,
            confidence=search_result.rank,
        )


    def get_remote_id_from_data(self, data):
        pass

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
