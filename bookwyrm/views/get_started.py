""" Helping new users figure out the lay of the land """
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import models
from bookwyrm.connectors import connector_manager


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class GetStarted(View):
    """ a book! this is the stuff """

    def get(self, request):
        """ info about a book """
        query = request.GET.get('query')
        book_results = []
        if query:
            book_results = connector_manager.local_search(query, raw=True)[:5]
        if len(book_results) < 5:
            popular_books = models.Edition.objects.exclude(
                parent_work__in=[b.parent_work for b in book_results],
            ).annotate(
                Count("shelfbook")
            ).order_by("-shelfbook__count")[: 5 - len(book_results)]


        data = {
            "book_results": book_results,
            "popular_books": popular_books,
        }
        return TemplateResponse(request, "get_started/books.html", data)
