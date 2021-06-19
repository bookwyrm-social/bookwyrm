""" isbn search view """
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.views import View

from bookwyrm.connectors import connector_manager
from .helpers import is_api_request

# pylint: disable= no-self-use
class Isbn(View):
    """search a book by isbn"""

    def get(self, request, isbn):
        """info about a book"""
        book_results = connector_manager.isbn_local_search(isbn)

        if is_api_request(request):
            return JsonResponse([r.json() for r in book_results], safe=False)

        data = {
            "results": book_results,
            "query": isbn,
        }
        return TemplateResponse(request, "isbn_search_results.html", data)
