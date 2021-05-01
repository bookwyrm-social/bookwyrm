""" search views"""
import re

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models.functions import Greatest
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.views import View

from bookwyrm import models
from bookwyrm.connectors import connector_manager
from bookwyrm.utils import regex
from .helpers import is_api_request, privacy_filter
from .helpers import handle_remote_webfinger


# pylint: disable= no-self-use
class Search(View):
    """search users or books"""

    def get(self, request):
        """that search bar up top"""
        query = request.GET.get("q")
        min_confidence = request.GET.get("min_confidence", 0.1)
        search_type = request.GET.get("type")

        if is_api_request(request):
            # only return local book results via json so we don't cascade
            book_results = connector_manager.local_search(
                query, min_confidence=min_confidence
            )
            return JsonResponse([r.json() for r in book_results], safe=False)

        if not search_type:
            search_type = "user" if "@" in query else "book"

        endpoints = {
            "book": book_search,
            "user": user_search,
            "list": list_search,
        }
        if not search_type in endpoints:
            search_type = "book"
        endpoint = endpoints[search_type]

        data = {"query": query or "", "type": search_type}
        results = endpoint(query, request.user, min_confidence) if query else {}

        return TemplateResponse(
            request, "search/{:s}.html".format(search_type), {**data, **results}
        )


def book_search(query, _, min_confidence):
    """that search bar up top"""

    return {
        "results": connector_manager.search(query, min_confidence=min_confidence),
    }


def user_search(query, viewer, _):
    """that search bar up top"""
    # logged out viewers can't search users
    if not viewer.is_authenticated:
        return {}

    # use webfinger for mastodon style account@domain.com username to load the user if
    # they don't exist locally (handle_remote_webfinger will check the db)
    if re.match(regex.full_username, query):
        handle_remote_webfinger(query)

    return {
        "results": (
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
            .order_by("-similarity")[:10]
        ),
    }


def list_search(query, viewer, _):
    """any relevent lists?"""
    return {
        "results": (
            privacy_filter(
                viewer,
                models.List.objects,
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
            .order_by("-similarity")[:10]
        ),
    }
