"""the good stuff! the books!"""

from typing import Any

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import forms, models
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.settings import PAGE_LENGTH
from bookwyrm.views import Book
from bookwyrm.views.helpers import is_api_request, redirect_to_referer
from bookwyrm.views.list.list import get_list_suggestions


# pylint: disable=no-self-use
class SuggestionList(View):
    """book list page"""

    def get(
        self, request: HttpRequest, book_id: int, **kwargs: Any
    ) -> ActivitypubResponse | TemplateResponse:
        """display a book list"""
        add_failed = kwargs.get("add_failed", False)
        add_succeeded = kwargs.get("add_succeeded", False)

        work = models.Work.objects.filter(
            Q(id=book_id) | Q(editions=book_id)
        ).distinct()
        work = work.first()

        book_list = get_object_or_404(models.SuggestionList, suggests_for=work)

        if is_api_request(request):
            return ActivitypubResponse(book_list.to_activity(**request.GET))

        items = (
            book_list.suggestionlistitem_set.prefetch_related(
                "user", "book", "book__authors"
            )
            .annotate(endorsement_count=Count("endorsement"))
            .order_by("-endorsement_count")
        )

        paginated = Paginator(items, PAGE_LENGTH)

        page = paginated.get_page(request.GET.get("page"))

        embed_key = str(book_list.embed_key.hex)  # type: ignore
        embed_url = reverse("embed-list", args=[book_list.id, embed_key])
        embed_url = request.build_absolute_uri(embed_url)

        if request.GET:
            embed_url = f"{embed_url}?{request.GET.urlencode()}"

        query = request.GET.get("q", "")
        data = {
            "list": book_list,
            "work": book_list.suggests_for,
            "items": page,
            "page_range": paginated.get_elided_page_range(
                page.number, on_each_side=2, on_ends=1
            ),
            "query": query,
            "embed_url": embed_url,
            "add_failed": add_failed,
            "add_succeeded": add_succeeded,
            "add_book_url": reverse("book-add-suggestion", args=[book_id]),
            "remove_book_url": reverse("book-remove-suggestion", args=[book_id]),
        }

        if request.user.is_authenticated:
            data["suggested_books"] = get_list_suggestions(
                book_list, request.user, query=query, ignore_book=book_list.suggests_for
            )
        return TemplateResponse(request, "lists/list.html", data)

    @method_decorator(login_required, name="dispatch")
    def post(
        self,
        request: HttpRequest,
        book_id: int,  # pylint: disable=unused-argument
    ) -> Any:
        """create a suggestion_list"""
        form = forms.SuggestionListForm(request.POST)

        if not form.is_valid():
            return redirect_to_referer(request)
        # saving in two steps means django uses the model's custom save functionality,
        # which adds an embed key and fixes the privacy and curation settings
        suggestion_list = form.save(request, commit=False)
        suggestion_list.save()

        return redirect_to_referer(request)


@login_required
@require_POST
def book_add_suggestion(request: HttpRequest, book_id: int) -> Any:
    """put a book on the suggestion list"""
    _ = get_object_or_404(
        models.SuggestionList, suggests_for=book_id, id=request.POST.get("book_list")
    )

    form = forms.SuggestionListItemForm(request.POST)
    if not form.is_valid():
        return Book().get(request, book_id, add_failed=True)

    form.save(request)

    return redirect_to_referer(request)


@require_POST
@login_required
def book_remove_suggestion(request: HttpRequest, book_id: int) -> Any:
    """remove a book from a suggestion list"""
    item = get_object_or_404(
        models.SuggestionListItem,
        id=request.POST.get("item"),
        book_list__suggests_for=book_id,
    )
    item.raise_not_deletable(request.user)

    with transaction.atomic():
        item.delete()

    return redirect_to_referer(request)


@require_POST
@login_required
def endorse_suggestion(request: HttpRequest, book_id: int, item_id: int) -> Any:
    """endorse a suggestion"""
    item = get_object_or_404(
        models.SuggestionListItem, id=item_id, book_list__suggests_for=book_id
    )
    if request.user not in item.endorsement.all():
        item.endorse(request.user)
    else:
        item.unendorse(request.user)
    return redirect_to_referer(request)
