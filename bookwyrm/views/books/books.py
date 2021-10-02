""" the good stuff! the books! """
from uuid import uuid4

from django.contrib.auth.decorators import login_required, permission_required
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db.models import Avg, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import forms, models
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.connectors import connector_manager
from bookwyrm.connectors.abstract_connector import get_image
from bookwyrm.settings import PAGE_LENGTH
from bookwyrm.views.helpers import is_api_request, privacy_filter


# pylint: disable=no-self-use
class Book(View):
    """a book! this is the stuff"""

    def get(self, request, book_id, user_statuses=False):
        """info about a book"""
        if is_api_request(request):
            book = get_object_or_404(
                models.Book.objects.select_subclasses(), id=book_id
            )
            return ActivitypubResponse(book.to_activity())

        user_statuses = user_statuses if request.user.is_authenticated else False

        # it's safe to use this OR because edition and work and subclasses of the same
        # table, so they never have clashing IDs
        book = (
            models.Edition.viewer_aware_objects(request.user)
            .filter(Q(id=book_id) | Q(parent_work__id=book_id))
            .order_by("-edition_rank")
            .select_related("parent_work")
            .prefetch_related("authors")
            .first()
        )

        if not book or not book.parent_work:
            raise Http404()

        # all reviews for all editions of the book
        reviews = privacy_filter(
            request.user, models.Review.objects.filter(book__parent_work__editions=book)
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

        lists = privacy_filter(
            request.user,
            models.List.objects.filter(
                listitem__approved=True,
                listitem__book__in=book.parent_work.editions.all(),
            ),
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
        }

        if request.user.is_authenticated:
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
        image_file = get_image(url)
    except:  # pylint: disable=bare-except
        return None
    if not image_file:
        return None
    image_name = str(uuid4()) + "." + url.split(".")[-1]
    image_content = ContentFile(image_file.content)
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


@require_POST
def resolve_book(request):
    """figure out the local path to a book from a remote_id"""
    remote_id = request.POST.get("remote_id")
    connector = connector_manager.get_or_create_connector(remote_id)
    book = connector.get_or_create_book(remote_id)

    return redirect("book", book.id)
