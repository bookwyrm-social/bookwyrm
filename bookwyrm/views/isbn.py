""" isbn search view """
from django.http import HttpResponseNotFound
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import forms, models
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
            "title": "ISBN Search Results",
            "results": book_results,
            "query": isbn,
        }
        return TemplateResponse(request, "isbn_search_results.html", data)
