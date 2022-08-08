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
                [book_search.format_search_result(r) for r in book_results[:10]],
                safe=False,
            )

        paginated = Paginator(book_results, PAGE_LENGTH)
        page = paginated.get_page(request.GET.get("page"))
        data = {
            "results": page,
            "page_range": paginated.get_elided_page_range(
                page.number, on_each_side=2, on_ends=1
            ),
            "query": isbn,
            "type": "book",
        }
        return TemplateResponse(request, "search/book.html", data)
