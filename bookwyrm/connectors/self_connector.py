''' using a bookwyrm instance as a source of book data '''
from django.contrib.postgres.search import SearchRank, SearchVector
from django.db.models import F

from bookwyrm import models
from .abstract_connector import AbstractConnector, SearchResult


class Connector(AbstractConnector):
    ''' instantiate a connector  '''
    def search(self, query, min_confidence=0.1):
        ''' right now you can't search bookwyrm sorry, but when
        that gets implemented it will totally rule '''
        vector = SearchVector('title', weight='A') +\
            SearchVector('subtitle', weight='B') +\
            SearchVector('author_text', weight='C') +\
            SearchVector('isbn_13', weight='A') +\
            SearchVector('isbn_10', weight='A') +\
            SearchVector('openlibrary_key', weight='C') +\
            SearchVector('goodreads_key', weight='C') +\
            SearchVector('asin', weight='C') +\
            SearchVector('oclc_number', weight='C') +\
            SearchVector('remote_id', weight='C') +\
            SearchVector('description', weight='D') +\
            SearchVector('series', weight='D')

        results = models.Edition.objects.annotate(
            search=vector
        ).annotate(
            rank=SearchRank(vector, query)
        ).filter(
            rank__gt=min_confidence
        ).order_by('-rank')

        # remove non-default editions, if possible
        results = results.filter(parent_work__default_edition__id=F('id')) \
                    or results

        search_results = []
        for book in results[:10]:
            search_results.append(
                self.format_search_result(book)
            )
        return search_results


    def format_search_result(self, search_result):
        return SearchResult(
            title=search_result.title,
            key=search_result.remote_id,
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
