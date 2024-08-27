""" the good stuff! the books! """
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import forms, models
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.settings import PAGE_LENGTH
from bookwyrm.views import Book
from bookwyrm.views.helpers import is_api_request
from bookwyrm.views.list.list import get_list_suggestions

# pylint: disable=no-self-use
class SuggestionList(View):
    """book list page"""

    def get(self, request, book_id, **kwargs):
        """display a book list"""
        add_failed = kwargs.get("add_failed", False)
        add_succeeded = kwargs.get("add_succeeded", False)

        book_list = get_object_or_404(models.SuggestionList, suggests_for=book_id)

        if is_api_request(request):
            return ActivitypubResponse(book_list.to_activity(**request.GET))

        items = book_list.suggestionlistitem_set.prefetch_related(
            "user", "book", "book__authors"
        )

        paginated = Paginator(items, PAGE_LENGTH)

        page = paginated.get_page(request.GET.get("page"))

        embed_key = str(book_list.embed_key.hex)
        embed_url = reverse("embed-list", args=[book_list.id, embed_key])
        embed_url = request.build_absolute_uri(embed_url)

        if request.GET:
            embed_url = f"{embed_url}?{request.GET.urlencode()}"

        query = request.GET.get("q", "")
        data = {
            "list": book_list,
            "items": page,
            "page_range": paginated.get_elided_page_range(
                page.number, on_each_side=2, on_ends=1
            ),
            "query": query,
            "embed_url": embed_url,
            "add_failed": add_failed,
            "add_succeeded": add_succeeded,
        }

        if request.user.is_authenticated:
            data["suggested_books"] = get_list_suggestions(
                book_list, request.user, query=query, ignore_book=book_list.suggests_for
            )
        return TemplateResponse(request, "lists/list.html", data)

    @method_decorator(login_required, name="dispatch")
    def post(self, request, book_id):
        """create a suggestion_list"""
        form = forms.SuggestionListForm(request.POST)
        book = get_object_or_404(models.Edition, id=book_id)

        if not form.is_valid():
            return redirect("book", book.id)
        # saving in two steps means django uses the model's custom save functionality,
        # which adds an embed key and fixes the privacy and curation settings
        suggestion_list = form.save(request, commit=False)
        suggestion_list.save()

        return redirect("book", book.id)


@login_required
@require_POST
@transaction.atomic
def book_add_suggestion(request, book_id):
    """put a book on the suggestion list"""
    _ = get_object_or_404(
        models.SuggestionList, suggests_for=book_id, id=request.POST.get("book_list")
    )

    form = forms.SuggestionListItemForm(request.POST)
    if not form.is_valid():
        return Book().get(request, book_id, add_failed=True)

    item = form.save(request, commit=False)
    item.save()

    return Book().get(request, book_id, add_succeeded=True)
