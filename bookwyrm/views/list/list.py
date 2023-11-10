""" book list views"""
from typing import Optional

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, DecimalField, Q, Max
from django.db.models.functions import Coalesce
from django.http import HttpResponseBadRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import book_search, forms, models
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.settings import PAGE_LENGTH
from bookwyrm.views.helpers import (
    is_api_request,
    maybe_redirect_local_path,
    redirect_to_referer,
)


# pylint: disable=no-self-use
class List(View):
    """book list page"""

    def get(self, request, list_id, **kwargs):
        """display a book list"""
        add_failed = kwargs.get("add_failed", False)
        add_succeeded = kwargs.get("add_succeeded", False)

        book_list = get_object_or_404(models.List, id=list_id)
        book_list.raise_visible_to_user(request.user)

        if is_api_request(request):
            return ActivitypubResponse(book_list.to_activity(**request.GET))

        if redirect_option := maybe_redirect_local_path(request, book_list):
            return redirect_option

        items = book_list.listitem_set.filter(approved=True).prefetch_related(
            "user", "book", "book__authors"
        )
        items = sort_list(request, items)

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
            "pending_count": book_list.listitem_set.filter(approved=False).count(),
            "list_form": forms.ListForm(instance=book_list),
            "query": query,
            "sort_form": forms.SortListForm(request.GET),
            "embed_url": embed_url,
            "add_failed": add_failed,
            "add_succeeded": add_succeeded,
        }

        if request.user.is_authenticated:
            data["suggested_books"] = get_list_suggestions(
                book_list, request.user, query=query
            )
        return TemplateResponse(request, "lists/list.html", data)

    @method_decorator(login_required, name="dispatch")
    def post(self, request, list_id):
        """edit a list"""
        book_list = get_object_or_404(models.List, id=list_id)

        form = forms.ListForm(request.POST, instance=book_list)
        if not form.is_valid():
            # this shouldn't happen
            raise Exception(form.errors)
        book_list = form.save(request)
        if not book_list.curation == "group":
            book_list.group = None
            book_list.save(broadcast=False)

        return redirect_to_referer(request, book_list.local_path)


def get_list_suggestions(book_list, user, query=None, num_suggestions=5):
    """What books might a user want to add to a list"""
    if query:
        # search for books
        return book_search.search(
            query,
            filters=[~Q(parent_work__editions__in=book_list.books.all())],
        )
    # just suggest whatever books are nearby
    suggestions = user.shelfbook_set.filter(
        ~Q(book__in=book_list.books.all())
    ).distinct()[:num_suggestions]
    suggestions = [s.book for s in suggestions[:num_suggestions]]
    if len(suggestions) < num_suggestions:
        others = [
            s.default_edition
            for s in models.Work.objects.filter(
                ~Q(editions__in=book_list.books.all()),
            )
            .distinct()
            .order_by("-updated_date")[:num_suggestions]
        ]
        # get 'num_suggestions' unique items
        suggestions = list(set(suggestions + others))[:num_suggestions]
    return suggestions


def sort_list(request, items):
    """helper to handle the surprisingly involved sorting"""
    # sort_by shall be "order" unless a valid alternative is given
    sort_by = request.GET.get("sort_by", "order")
    if sort_by not in ("order", "sort_title", "rating"):
        sort_by = "order"

    # direction shall be "ascending" unless a valid alternative is given
    direction = request.GET.get("direction", "ascending")
    if direction not in ("ascending", "descending"):
        direction = "ascending"

    directional_sort_by = {
        "order": "order",
        "sort_title": "book__sort_title",
        "rating": "average_rating",
    }[sort_by]
    if direction == "descending":
        directional_sort_by = "-" + directional_sort_by

    if sort_by == "rating":
        items = items.annotate(
            average_rating=Avg(
                Coalesce("book__review__rating", 0.0),
                output_field=DecimalField(),
            )
        )
    return items.order_by(directional_sort_by)


@require_POST
@login_required
def save_list(request, list_id):
    """save a list"""
    book_list = get_object_or_404(models.List, id=list_id)
    request.user.saved_lists.add(book_list)
    return redirect_to_referer(request, "list", list_id)


@require_POST
@login_required
def unsave_list(request, list_id):
    """unsave a list"""
    book_list = get_object_or_404(models.List, id=list_id)
    request.user.saved_lists.remove(book_list)
    return redirect_to_referer(request, "list", list_id)


@require_POST
@login_required
def delete_list(request, list_id):
    """delete a list"""
    book_list = get_object_or_404(models.List, id=list_id)

    # only the owner or a moderator can delete a list
    book_list.raise_not_deletable(request.user)

    book_list.delete()
    return redirect("/list")


@require_POST
@login_required
@transaction.atomic
def add_book(request):
    """put a book on a list"""
    book_list = get_object_or_404(models.List, id=request.POST.get("book_list"))
    # make sure the user is allowed to submit to this list
    book_list.raise_visible_to_user(request.user)
    if request.user != book_list.user and book_list.curation == "closed":
        raise PermissionDenied()

    is_group_member = models.GroupMember.objects.filter(
        group=book_list.group, user=request.user
    ).exists()

    form = forms.ListItemForm(request.POST)
    if not form.is_valid():
        return List().get(request, book_list.id, add_failed=True)

    item = form.save(request, commit=False)

    if book_list.curation == "curated":
        # make a pending entry at the end of the list
        order_max = (book_list.listitem_set.aggregate(Max("order"))["order__max"]) or 0
        item.approved = is_group_member or request.user == book_list.user
    else:
        # add the book at the latest order of approved books, before pending books
        order_max = (
            book_list.listitem_set.filter(approved=True).aggregate(Max("order"))[
                "order__max"
            ]
        ) or 0
        increment_order_in_reverse(book_list.id, order_max + 1)
    item.order = order_max + 1
    item.save()

    return List().get(request, book_list.id, add_succeeded=True)


@require_POST
@login_required
def remove_book(request, list_id):
    """remove a book from a list"""

    book_list = get_object_or_404(models.List, id=list_id)
    item = get_object_or_404(models.ListItem, id=request.POST.get("item"))

    item.raise_not_deletable(request.user)

    with transaction.atomic():
        deleted_order = item.order
        item.delete()
        normalize_book_list_ordering(book_list.id, start=deleted_order)

    return redirect_to_referer(request, "list", list_id)


@require_POST
@login_required
def set_book_position(request, list_item_id):
    """
    Action for when the list user manually specifies a list position, takes
    special care with the unique ordering per list.
    """
    list_item = get_object_or_404(models.ListItem, id=list_item_id)
    try:
        int_position = int(request.POST.get("position"))
    except ValueError:
        return HttpResponseBadRequest("bad value for position. should be an integer")

    if int_position < 1:
        return HttpResponseBadRequest("position cannot be less than 1")

    book_list = list_item.book_list

    # the max position to which a book may be set is the highest order for
    # books which are approved
    order_max = book_list.listitem_set.filter(approved=True).aggregate(Max("order"))[
        "order__max"
    ]

    int_position = min(int_position, order_max)

    original_order = list_item.order
    if original_order == int_position:
        # no change
        return HttpResponse(status=204)

    with transaction.atomic():
        if original_order > int_position:
            list_item.order = -1
            list_item.save()
            increment_order_in_reverse(book_list.id, int_position, original_order)
        else:
            list_item.order = -1
            list_item.save()
            decrement_order(book_list.id, original_order, int_position)

        list_item.order = int_position
        list_item.save()

    return redirect_to_referer(request, book_list.local_path)


@transaction.atomic
def increment_order_in_reverse(
    book_list_id: int, start: int, end: Optional[int] = None
):
    """increase the order number for every item in a list"""
    try:
        book_list = models.List.objects.get(id=book_list_id)
    except models.List.DoesNotExist:
        return
    items = book_list.listitem_set.filter(order__gte=start)
    if end is not None:
        items = items.filter(order__lt=end)
    items = items.order_by("-order")
    for item in items:
        item.order += 1
        item.save()


@transaction.atomic
def decrement_order(book_list_id, start, end):
    """decrement the order value for every item in a list"""
    try:
        book_list = models.List.objects.get(id=book_list_id)
    except models.List.DoesNotExist:
        return
    items = book_list.listitem_set.filter(order__gt=start, order__lte=end).order_by(
        "order"
    )
    for item in items:
        item.order -= 1
        item.save()


@transaction.atomic
def normalize_book_list_ordering(book_list_id, start=0, add_offset=0):
    """gives each book in a list the proper sequential order number"""
    try:
        book_list = models.List.objects.get(id=book_list_id)
    except models.List.DoesNotExist:
        return
    items = book_list.listitem_set.filter(order__gt=start).order_by("order")
    for i, item in enumerate(items, start):
        effective_order = i + add_offset
        if item.order != effective_order:
            item.order = effective_order
            item.save()
