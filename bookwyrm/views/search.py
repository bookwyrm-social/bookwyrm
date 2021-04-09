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
    """ search users or books """

    def get(self, request):
        """ that search bar up top """
        query = request.GET.get("q")
        min_confidence = request.GET.get("min_confidence", 0.1)

        if is_api_request(request):
            # only return local book results via json so we don't cascade
            book_results = connector_manager.local_search(
                query, min_confidence=min_confidence
            )
            return JsonResponse([r.json() for r in book_results], safe=False)

        # use webfinger for mastodon style account@domain.com username
        if query and re.match(regex.full_username, query):
            handle_remote_webfinger(query)

        # do a user search
        user_results = (
            models.User.viewer_aware_objects(request.user)
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
        )

        # any relevent lists?
        list_results = (
            privacy_filter(
                request.user,
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
        )

        book_results = connector_manager.search(query, min_confidence=min_confidence)
        data = {
            "book_results": book_results,
            "user_results": user_results,
            "list_results": list_results,
            "query": query or "",
        }
        return TemplateResponse(request, "search_results.html", data)
