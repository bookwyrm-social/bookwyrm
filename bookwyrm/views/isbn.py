""" isbn search view """
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.views import View

from bookwyrm import book_search
from bookwyrm.settings import PAGE_LENGTH
from .helpers import is_api_request

# pylint: disable= no-self-use
class Isbn(View):
    """search a book by isbn"""

    def get(self, request, isbn):
        """info about a book"""
        book_results = book_search.isbn_search(isbn)

        if is_api_request(request):
            return JsonResponse(
                [book_search.format_search_result(r) for r in book_results], safe=False
            )

        paginated = Paginator(book_results, PAGE_LENGTH).get_page(
            request.GET.get("page")
        )
        data = {
            "results": [{"results": paginated}],
            "query": isbn,
            "type": "book",
        }
        return TemplateResponse(request, "search/book.html", data)
