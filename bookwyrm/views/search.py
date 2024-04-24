""" search views"""

import re

from django.contrib.postgres.search import TrigramSimilarity, SearchRank, SearchQuery
from django.core.paginator import Paginator
from django.db.models import F
from django.db.models.functions import Greatest
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.views import View

from csp.decorators import csp_update

from bookwyrm import models
from bookwyrm.connectors import connector_manager
from bookwyrm.book_search import search, format_search_result
from bookwyrm.settings import PAGE_LENGTH, INSTANCE_ACTOR_USERNAME
from bookwyrm.utils import regex
from .helpers import is_api_request
from .helpers import handle_remote_webfinger


# pylint: disable= no-self-use
class Search(View):
    """search users or books"""

    @csp_update(IMG_SRC="*")
    def get(self, request):
        """that search bar up top"""
        if is_api_request(request):
            return api_book_search(request)

        query = request.GET.get("q")
        if not query:
            return TemplateResponse(request, "search/book.html")

        search_type = request.GET.get("type")
        if query and not search_type:
            search_type = "user" if "@" in query else "book"

        endpoints = {
            "book": book_search,
            "author": author_search,
            "user": user_search,
            "list": list_search,
        }
        if not search_type in endpoints:
            search_type = "book"

        return endpoints[search_type](request)


def api_book_search(request):
    """Return books via API response"""
    query = request.GET.get("q")
    query = isbn_check_and_format(query)
    min_confidence = request.GET.get("min_confidence", 0)
    # only return local book results via json so we don't cascade
    book_results = search(query, min_confidence=min_confidence)
    return JsonResponse(
        [format_search_result(r) for r in book_results[:10]], safe=False
    )


def book_search(request):
    """the real business is elsewhere"""
    query = request.GET.get("q")
    # check if query is isbn
    query = isbn_check_and_format(query)
    min_confidence = request.GET.get("min_confidence", 0)
    search_remote = request.GET.get("remote", False) and request.user.is_authenticated

    # try a local-only search
    local_results = search(query, min_confidence=min_confidence)
    paginated = Paginator(local_results, PAGE_LENGTH)
    page = paginated.get_page(request.GET.get("page"))
    data = {
        "query": query,
        "results": page,
        "type": "book",
        "remote": search_remote,
        "page_range": paginated.get_elided_page_range(
            page.number, on_each_side=2, on_ends=1
        ),
    }
    # if a logged in user requested remote results or got no local results, try remote
    if request.user.is_authenticated and (not local_results or search_remote):
        data["remote_results"] = connector_manager.search(
            query, min_confidence=min_confidence
        )
        data["remote"] = True
    return TemplateResponse(request, "search/book.html", data)


def author_search(request):
    """search for an author"""
    query = request.GET.get("q").strip()
    search_query = SearchQuery(query, config="simple")
    min_confidence = 0

    results = (
        models.Author.objects.filter(search_vector=search_query)
        .annotate(rank=SearchRank(F("search_vector"), search_query))
        .filter(rank__gt=min_confidence)
        .order_by("-rank")
    )

    paginated = Paginator(results, PAGE_LENGTH)
    page = paginated.get_page(request.GET.get("page"))

    data = {
        "type": "author",
        "query": query,
        "results": page,
        "page_range": paginated.get_elided_page_range(
            page.number, on_each_side=2, on_ends=1
        ),
    }
    return TemplateResponse(request, "search/author.html", data)


def user_search(request):
    """user search: search for a user"""
    viewer = request.user
    query = request.GET.get("q")
    query = query.strip()
    data = {"type": "user", "query": query}

    # use webfinger for mastodon style account@domain.com username to load the user if
    # they don't exist locally (handle_remote_webfinger will check the db)
    if re.match(regex.FULL_USERNAME, query) and viewer.is_authenticated:
        handle_remote_webfinger(query)

    results = (
        models.User.viewer_aware_objects(viewer)
        .annotate(
            similarity=Greatest(
                TrigramSimilarity("username", query),
                TrigramSimilarity("localname", query),
            )
        )
        .filter(
            similarity__gt=0.5,
        )
        .exclude(localname=INSTANCE_ACTOR_USERNAME)
        .order_by("-similarity")
    )

    # don't expose remote users
    if not viewer.is_authenticated:
        results = results.filter(local=True)

    paginated = Paginator(results, PAGE_LENGTH)
    page = paginated.get_page(request.GET.get("page"))
    data["results"] = page
    data["page_range"] = paginated.get_elided_page_range(
        page.number, on_each_side=2, on_ends=1
    )
    return TemplateResponse(request, "search/user.html", data)


def list_search(request):
    """any relevent lists?"""
    query = request.GET.get("q")
    data = {"query": query, "type": "list"}
    results = (
        models.List.privacy_filter(
            request.user,
            privacy_levels=["public", "followers"],
        )
        .annotate(
            similarity=Greatest(
                TrigramSimilarity("name", query),
                TrigramSimilarity("description", query),
            )
        )
        .filter(
            similarity__gt=0.1,
        )
        .order_by("-similarity")
    )
    paginated = Paginator(results, PAGE_LENGTH)
    page = paginated.get_page(request.GET.get("page"))
    data["results"] = page
    data["page_range"] = paginated.get_elided_page_range(
        page.number, on_each_side=2, on_ends=1
    )
    return TemplateResponse(request, "search/list.html", data)


def isbn_check_and_format(query):
    """isbn10 or isbn13 check, if so remove separators"""
    if query:
        su_num = re.sub(r"(?<=\d)\D(?=\d|[xX])", "", query)
        if len(su_num) == 13 and su_num.isdecimal():
            # Multiply every other digit by  3
            # Add these numbers and the other digits
            product = sum(int(ch) for ch in su_num[::2]) + sum(
                int(ch) * 3 for ch in su_num[1::2]
            )
            if product % 10 == 0:
                return su_num
        elif (
            len(su_num) == 10
            and su_num[:-1].isdecimal()
            and (su_num[-1].isdecimal() or su_num[-1].lower() == "x")
        ):
            product = 0
            # Iterate through code_string
            for i in range(9):
                # for each character, multiply by a different decreasing number: 10 - x
                product = product + int(su_num[i]) * (10 - i)
            # Handle last character
            if su_num[9].lower() == "x":
                product += 10
            else:
                product += int(su_num[9])
            if product % 11 == 0:
                return su_num
    return query
