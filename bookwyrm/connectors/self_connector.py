""" using a bookwyrm instance as a source of book data """
from functools import reduce
import operator

from django.contrib.postgres.search import SearchRank, SearchVector
from django.db.models import OuterRef, Subquery, F, Q

from bookwyrm import models
from .abstract_connector import AbstractConnector, SearchResult


class Connector(AbstractConnector):
    """instantiate a connector"""

    # pylint: disable=arguments-differ
    def search(self, query, min_confidence=0.1, raw=False, filters=None):
        """search your local database"""
        filters = filters or []
        if not query:
            return []
        # first, try searching unqiue identifiers
        results = search_identifiers(query, *filters)
        if not results:
            # then try searching title/author
            results = search_title_author(query, min_confidence, *filters)
        search_results = []
        for result in results:
            if raw:
                search_results.append(result)
            else:
                search_results.append(self.format_search_result(result))
            if len(search_results) >= 10:
                break
        if not raw:
            search_results.sort(key=lambda r: r.confidence, reverse=True)
        return search_results

    def isbn_search(self, query, raw=False):
        """search your local database"""
        if not query:
            return []

        filters = [{f: query} for f in ["isbn_10", "isbn_13"]]
        results = models.Edition.objects.filter(
            reduce(operator.or_, (Q(**f) for f in filters))
        ).distinct()

        # when there are multiple editions of the same work, pick the default.
        # it would be odd for this to happen.

        default_editions = models.Edition.objects.filter(
            parent_work=OuterRef("parent_work")
        ).order_by("-edition_rank")
        results = (
            results.annotate(
                default_id=Subquery(default_editions.values("id")[:1])
            ).filter(default_id=F("id"))
            or results
        )

        search_results = []
        for result in results:
            if raw:
                search_results.append(result)
            else:
                search_results.append(self.format_search_result(result))
            if len(search_results) >= 10:
                break
        return search_results

    def format_search_result(self, search_result):
        cover = None
        if search_result.cover:
            cover = "%s%s" % (self.covers_url, search_result.cover)

        return SearchResult(
            title=search_result.title,
            key=search_result.remote_id,
            author=search_result.author_text,
            year=search_result.published_date.year
            if search_result.published_date
            else None,
            connector=self,
            cover=cover,
            confidence=search_result.rank if hasattr(search_result, "rank") else 1,
        )

    def format_isbn_search_result(self, search_result):
        return self.format_search_result(search_result)

    def is_work_data(self, data):
        pass

    def get_edition_from_work_data(self, data):
        pass

    def get_work_from_edition_data(self, data):
        pass

    def get_authors_from_data(self, data):
        return None

    def parse_isbn_search_data(self, data):
        """it's already in the right format, don't even worry about it"""
        return data

    def parse_search_data(self, data):
        """it's already in the right format, don't even worry about it"""
        return data

    def expand_book_data(self, book):
        pass


def search_identifiers(query, *filters):
    """tries remote_id, isbn; defined as dedupe fields on the model"""
    or_filters = [
        {f.name: query}
        for f in models.Edition._meta.get_fields()
        if hasattr(f, "deduplication_field") and f.deduplication_field
    ]
    results = models.Edition.objects.filter(
        *filters, reduce(operator.or_, (Q(**f) for f in or_filters))
    ).distinct()
    if results.count() <= 1:
        return results

    # when there are multiple editions of the same work, pick the default.
    # it would be odd for this to happen.
    default_editions = models.Edition.objects.filter(
        parent_work=OuterRef("parent_work")
    ).order_by("-edition_rank")
    return (
        results.annotate(default_id=Subquery(default_editions.values("id")[:1])).filter(
            default_id=F("id")
        )
        or results
    )


def search_title_author(query, min_confidence, *filters):
    """searches for title and author"""
    vector = (
        SearchVector("title", weight="A")
        + SearchVector("subtitle", weight="B")
        + SearchVector("authors__name", weight="C")
        + SearchVector("series", weight="D")
    )

    results = (
        models.Edition.objects.annotate(rank=SearchRank(vector, query))
        .filter(*filters, rank__gt=min_confidence)
        .order_by("-rank")
    )

    # when there are multiple editions of the same work, pick the closest
    editions_of_work = results.values("parent_work__id").values_list("parent_work__id")

    # filter out multiple editions of the same work
    for work_id in set(editions_of_work):
        editions = results.filter(parent_work=work_id)
        default = editions.order_by("-edition_rank").first()
        default_rank = default.rank if default else 0
        # if mutliple books have the top rank, pick the default edition
        if default_rank == editions.first().rank:
            yield default
        else:
            yield editions.first()
