""" the good stuff! the books! """
from uuid import uuid4

from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Q, Max
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import forms, models
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.connectors import connector_manager, ConnectorException
from bookwyrm.connectors.abstract_connector import get_image
from bookwyrm.settings import PAGE_LENGTH
from bookwyrm.views.helpers import is_api_request, maybe_redirect_local_path
from bookwyrm.views.list.list import get_list_suggestions, increment_order_in_reverse


# pylint: disable=no-self-use
class Book(View):
    """a book! this is the stuff"""

    def get(self, request, book_id, **kwargs):
        """info about a book"""
        if is_api_request(request):
            book = get_object_or_404(
                models.Book.objects.select_subclasses(), id=book_id
            )
            return ActivitypubResponse(book.to_activity())

        user_statuses = (
            kwargs.get("user_statuses", False)
            if request.user.is_authenticated
            else False
        )

        # it's safe to use this OR because edition and work and subclasses of the same
        # table, so they never have clashing IDs
        book = (
            models.Edition.viewer_aware_objects(request.user)
            .filter(Q(id=book_id) | Q(parent_work__id=book_id))
            .order_by("-edition_rank")
            .select_related("parent_work")
            .prefetch_related("authors", "file_links")
            .first()
        )

        if not book or not book.parent_work:
            raise Http404()

        if redirect_local_path := not user_statuses and maybe_redirect_local_path(
            request, book
        ):
            return redirect_local_path

        # all reviews for all editions of the book
        reviews = models.Review.privacy_filter(request.user).filter(
            book__parent_work__editions=book
        )

        # the reviews to show
        if user_statuses:
            if user_statuses == "review":
                queryset = book.review_set.select_subclasses()
            elif user_statuses == "comment":
                queryset = book.comment_set
            else:
                queryset = book.quotation_set
            queryset = queryset.filter(user=request.user, deleted=False)
        else:
            queryset = reviews.exclude(Q(content__isnull=True) | Q(content=""))
        queryset = queryset.select_related("user").order_by("-published_date")
        paginated = Paginator(queryset, PAGE_LENGTH)

        query = request.GET.get("suggestion_query", "")

        lists = models.List.privacy_filter(request.user,).filter(
            listitem__approved=True,
            listitem__book__in=book.parent_work.editions.all(),
        )
        data = {
            "book": book,
            "statuses": paginated.get_page(request.GET.get("page")),
            "review_count": reviews.count(),
            "ratings": reviews.filter(
                Q(content__isnull=True) | Q(content="")
            ).select_related("user")
            if not user_statuses
            else None,
            "rating": reviews.aggregate(Avg("rating"))["rating__avg"],
            "lists": lists,
            "update_error": kwargs.get("update_error", False),
            "query": query,
        }

        if request.user.is_authenticated:
            data["list_options"] = request.user.list_set.exclude(id__in=data["lists"])
            data["file_link_form"] = forms.FileLinkForm()
            readthroughs = models.ReadThrough.objects.filter(
                user=request.user,
                book=book,
            ).order_by("start_date")

            for readthrough in readthroughs:
                readthrough.progress_updates = (
                    readthrough.progressupdate_set.all().order_by("-updated_date")
                )
            data["readthroughs"] = readthroughs

            data["user_shelfbooks"] = models.ShelfBook.objects.filter(
                user=request.user, book=book
            ).select_related("shelf")

            data["other_edition_shelves"] = models.ShelfBook.objects.filter(
                ~Q(book=book),
                user=request.user,
                book__parent_work=book.parent_work,
            ).select_related("shelf", "book")

            filters = {"user": request.user, "deleted": False}
            data["user_statuses"] = {
                "review_count": book.review_set.filter(**filters).count(),
                "comment_count": book.comment_set.filter(**filters).count(),
                "quotation_count": book.quotation_set.filter(**filters).count(),
            }
            if hasattr(book, "suggestion_list"):
                data["suggested_books"] = get_list_suggestions(
                    book.suggestion_list,
                    request.user,
                    query=query,
                    ignore_id=book.id,
                )

        return TemplateResponse(request, "book/book.html", data)


@login_required
@require_POST
def upload_cover(request, book_id):
    """upload a new cover"""
    book = get_object_or_404(models.Edition, id=book_id)
    book.last_edited_by = request.user

    url = request.POST.get("cover-url")
    if url:
        image = set_cover_from_url(url)
        if image:
            book.cover.save(*image)

        return redirect(f"{book.local_path}?cover_error=True")

    form = forms.CoverForm(request.POST, request.FILES, instance=book)
    if not form.is_valid() or not form.files.get("cover"):
        return redirect(book.local_path)

    book.cover = form.files["cover"]
    book.save()

    return redirect(book.local_path)


def set_cover_from_url(url):
    """load it from a url"""
    try:
        image_content, extension = get_image(url)
    except:  # pylint: disable=bare-except
        return None
    if not image_content:
        return None
    image_name = str(uuid4()) + "." + extension
    return [image_name, image_content]


@login_required
@require_POST
@permission_required("bookwyrm.edit_book", raise_exception=True)
def add_description(request, book_id):
    """upload a new cover"""
    book = get_object_or_404(models.Edition, id=book_id)

    description = request.POST.get("description")

    book.description = description
    book.last_edited_by = request.user
    book.save(update_fields=["description", "last_edited_by"])

    return redirect("book", book.id)


@login_required
@require_POST
def resolve_book(request):
    """figure out the local path to a book from a remote_id"""
    remote_id = request.POST.get("remote_id")
    connector = connector_manager.get_or_create_connector(remote_id)
    book = connector.get_or_create_book(remote_id)

    return redirect("book", book.id)


@login_required
@require_POST
@permission_required("bookwyrm.edit_book", raise_exception=True)
# pylint: disable=unused-argument
def update_book_from_remote(request, book_id, connector_identifier):
    """load the remote data for this book"""
    connector = connector_manager.load_connector(
        get_object_or_404(models.Connector, identifier=connector_identifier)
    )
    book = get_object_or_404(models.Book.objects.select_subclasses(), id=book_id)

    try:
        connector.update_book_from_remote(book)
    except ConnectorException:
        # the remote source isn't available or doesn't know this book
        return Book().get(request, book_id, update_error=True)

    return redirect("book", book.id)


@login_required
@require_POST
def create_suggestion_list(request, book_id):
    """create a suggestion_list"""
    form = forms.SuggestionListForm(request.POST)
    book = get_object_or_404(models.Edition, id=book_id)

    if not form.is_valid():
        return redirect("book", book.id)
    suggestion_list = form.save(request, commit=False)

    # default values for the suggestion list
    suggestion_list.privacy = "public"
    suggestion_list.curation = "open"
    suggestion_list.save()

    return redirect("book", book.id)


@login_required
@require_POST
@transaction.atomic
def book_add_suggestion(request, book_id):
    """put a book on the suggestion list"""
    book_list = get_object_or_404(models.List, id=request.POST.get("book_list"))

    form = forms.ListItemForm(request.POST)
    if not form.is_valid():
        return Book().get(request, book_id, add_failed=True)

    item = form.save(request, commit=False)

    # add the book at the latest order of approved books, before pending books
    order_max = (
        book_list.listitem_set.filter(approved=True).aggregate(Max("order"))[
            "order__max"
        ]
    ) or 0
    increment_order_in_reverse(book_list.id, order_max + 1)
    item.order = order_max + 1
    item.save()

    return Book().get(request, book_id, add_succeeded=True)
