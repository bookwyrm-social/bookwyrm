""" using a bookwyrm instance as a source of book data """
from dataclasses import asdict, dataclass
from functools import reduce
import operator

from django.contrib.postgres.search import SearchRank, SearchQuery
from django.db.models import OuterRef, Subquery, F, Q

from bookwyrm import models
from bookwyrm import connectors
from bookwyrm.settings import MEDIA_FULL_URL


# pylint: disable=arguments-differ
def search(query, min_confidence=0, filters=None, return_first=False):
    """search your local database"""
    filters = filters or []
    if not query:
        return []
    # first, try searching unqiue identifiers
    results = search_identifiers(query, *filters, return_first=return_first)
    if not results:
        # then try searching title/author
        results = search_title_author(
            query, min_confidence, *filters, return_first=return_first
        )
    return results


def search_genre(active_genres, search_active_option):
    """Get our genre list and put them on the page. If the user made a query, also display the books."""


    # Check if there's actually a genre selected.
    if len(active_genres):

        results = []
        # AND Searching
        if search_active_option == "search_and":

            print("Searching using AND")
            base_qs = models.Work.objects.all()
            for gen in active_genres:
                results = base_qs.filter(genres__pk__contains=gen)
            results = get_first_edition_gen(results)
        #OR searching
        elif search_active_option == "search_or":

            for gen in active_genres:
                print("Item successful captured!")
                results.extend(models.Work.objects.filter(genres = gen))
                results = get_first_edition_gen(results)
        #EXCLUDE searching
        elif search_active_option == "search_exclude":
            base_qs = models.Work.objects.all()
            results = models.Work.objects.exclude(genres__pk__in = active_genres)
            results = get_first_edition_gen(results)


        print("Printing this enter:" + active_genres[0])
        for item in results:
            print(item)
        print("Active books successful")

    else:
        results = []
        print("Empty List")

    return results

def get_first_edition_gen(results):
    list_result = []
    for work in results:
        try:
            list_result.append(work.default_edition)
        except:
            #Ignore it if something went wrong somehow.
            continue

    return list_result


def isbn_search(query):
    """search your local database"""
    if not query:
        return []
    # Up-case the ISBN string to ensure any 'X' check-digit is correct
    # If the ISBN has only 9 characters, prepend missing zero
    query = query.strip().upper().rjust(10, "0")
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
        results.annotate(default_id=Subquery(default_editions.values("id")[:1])).filter(
            default_id=F("id")
        )
        or results
    )
    return results


def format_search_result(search_result):
    """convert a book object into a search result object"""
    cover = None
    if search_result.cover:
        cover = f"{MEDIA_FULL_URL}{search_result.cover}"

    return SearchResult(
        title=search_result.title,
        key=search_result.remote_id,
        author=search_result.author_text,
        year=search_result.published_date.year
        if search_result.published_date
        else None,
        cover=cover,
        confidence=search_result.rank if hasattr(search_result, "rank") else 1,
        connector="",
    ).json()


def search_identifiers(query, *filters, return_first=False):
    """tries remote_id, isbn; defined as dedupe fields on the model"""
    if connectors.maybe_isbn(query):
        # Oh did you think the 'S' in ISBN stood for 'standard'?
        normalized_isbn = query.strip().upper().rjust(10, "0")
        query = normalized_isbn
    # pylint: disable=W0212
    or_filters = [
        {f.name: query}
        for f in models.Edition._meta.get_fields()
        if hasattr(f, "deduplication_field") and f.deduplication_field
    ]
    results = models.Edition.objects.filter(
        *filters, reduce(operator.or_, (Q(**f) for f in or_filters))
    ).distinct()
    if results.count() <= 1:
        if return_first:
            return results.first()
        return results

    # when there are multiple editions of the same work, pick the default.
    # it would be odd for this to happen.
    default_editions = models.Edition.objects.filter(
        parent_work=OuterRef("parent_work")
    ).order_by("-edition_rank")
    results = (
        results.annotate(default_id=Subquery(default_editions.values("id")[:1])).filter(
            default_id=F("id")
        )
        or results
    )
    if return_first:
        return results.first()
    return results


def search_title_author(query, min_confidence, *filters, return_first=False):
    """searches for title and author"""
    query = SearchQuery(query, config="simple") | SearchQuery(query, config="english")
    results = (
        models.Edition.objects.filter(*filters, search_vector=query)
        .annotate(rank=SearchRank(F("search_vector"), query))
        .filter(rank__gt=min_confidence)
        .order_by("-rank")
    )

    # when there are multiple editions of the same work, pick the closest
    editions_of_work = results.values("parent_work__id").values_list("parent_work__id")

    # filter out multiple editions of the same work
    list_results = []
    for work_id in set(editions_of_work):
        editions = results.filter(parent_work=work_id)
        default = editions.order_by("-edition_rank").first()
        default_rank = default.rank if default else 0
        # if mutliple books have the top rank, pick the default edition
        if default_rank == editions.first().rank:
            result = default
        else:
            result = editions.first()

        if return_first:
            return result
        list_results.append(result)
    return list_results


@dataclass
class SearchResult:
    """standardized search result object"""

    title: str
    key: str
    connector: object
    #genres: str[str]
    view_link: str = None
    author: str = None
    year: str = None
    cover: str = None
    confidence: int = 1

    def __repr__(self):
        # pylint: disable=consider-using-f-string
        return "<SearchResult key={!r} title={!r} author={!r} confidence={!r}>".format(
            self.key, self.title, self.author, self.confidence
        )

    def json(self):
        """serialize a connector for json response"""
        serialized = asdict(self)
        del serialized["connector"]
        return serialized

@dataclass
class GenreResult:
    """How our genre will look like when requesting it from another instance."""

    id: str
    genre_name: str
    description: str
    name: str
    type: str
    connector: object


    def __repr__(self):
        # pylint: disable=consider-using-f-string
        return "<GenreInfo id={!r} genre_name={!r} name={!r} description={!r}>".format(
            self.id, self.genre_name, self.name, self.description
        )

    def json(self):
        """serialize a connector for json response"""
        serialized = asdict(self)
        del serialized["connector"]
        return serialized
