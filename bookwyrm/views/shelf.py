""" shelf views"""
from collections import namedtuple

from django.db import IntegrityError
from django.db.models import OuterRef, Subquery
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import forms, models
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.settings import PAGE_LENGTH
from .helpers import is_api_request, get_edition, get_user_from_username
from .helpers import handle_reading_status, privacy_filter


# pylint: disable=no-self-use
class Shelf(View):
    """shelf page"""

    def get(self, request, username, shelf_identifier=None):
        """display a shelf"""
        user = get_user_from_username(request.user, username)

        is_self = user == request.user

        if is_self:
            shelves = user.shelf_set
        else:
            shelves = privacy_filter(request.user, user.shelf_set)

        # get the shelf and make sure the logged in user should be able to see it
        if shelf_identifier:
            try:
                shelf = user.shelf_set.get(identifier=shelf_identifier)
            except models.Shelf.DoesNotExist:
                return HttpResponseNotFound()
            if not shelf.visible_to_user(request.user):
                return HttpResponseNotFound()
            books = shelf.books
        # this is a constructed "all books" view, with a fake "shelf" obj
        else:
            FakeShelf = namedtuple(
                "Shelf", ("identifier", "name", "user", "books", "privacy")
            )
            books = models.Edition.objects.filter(
                # privacy is ensured because the shelves are already filtered above
                shelfbook__shelf__in=shelves.all()
            ).distinct()
            shelf = FakeShelf("all", _("All books"), user, books, "public")

        if is_api_request(request):
            return ActivitypubResponse(shelf.to_activity(**request.GET))

        reviews = models.Review.objects.filter(
            user=user,
            rating__isnull=False,
            book__id=OuterRef("id"),
            deleted=False,
        ).order_by("-published_date")

        if not is_self:
            reviews = privacy_filter(request.user, reviews)

        books = books.annotate(
            rating=Subquery(reviews.values("rating")[:1])
        ).prefetch_related("authors")

        paginated = Paginator(
            books.order_by("-shelfbook__updated_date"),
            PAGE_LENGTH,
        )

        page = paginated.get_page(request.GET.get("page"))
        data = {
            "user": user,
            "is_self": is_self,
            "shelves": shelves.all(),
            "shelf": shelf,
            "books": page,
            "page_range": paginated.get_elided_page_range(
                page.number, on_each_side=2, on_ends=1
            ),
        }

        return TemplateResponse(request, "user/shelf/shelf.html", data)

    @method_decorator(login_required, name="dispatch")
    # pylint: disable=unused-argument
    def post(self, request, username, shelf_identifier):
        """edit a shelf"""
        try:
            shelf = request.user.shelf_set.get(identifier=shelf_identifier)
        except models.Shelf.DoesNotExist:
            return HttpResponseNotFound()

        if request.user != shelf.user:
            return HttpResponseBadRequest()
        if not shelf.editable and request.POST.get("name") != shelf.name:
            return HttpResponseBadRequest()

        form = forms.ShelfForm(request.POST, instance=shelf)
        if not form.is_valid():
            return redirect(shelf.local_path)
        shelf = form.save()
        return redirect(shelf.local_path)


@login_required
@require_POST
def create_shelf(request):
    """user generated shelves"""
    form = forms.ShelfForm(request.POST)
    if not form.is_valid():
        return redirect(request.headers.get("Referer", "/"))

    shelf = form.save()
    return redirect(shelf.local_path)


@login_required
@require_POST
def delete_shelf(request, shelf_id):
    """user generated shelves"""
    shelf = get_object_or_404(models.Shelf, id=shelf_id)
    if request.user != shelf.user or not shelf.editable:
        return HttpResponseBadRequest()

    shelf.delete()
    return redirect("user-shelves", request.user.localname)


@login_required
@require_POST
def shelve(request):
    """put a book on a user's shelf"""
    book = get_edition(request.POST.get("book"))

    desired_shelf = models.Shelf.objects.filter(
        identifier=request.POST.get("shelf"), user=request.user
    ).first()
    if not desired_shelf:
        return HttpResponseNotFound()

    change_from_current_identifier = request.POST.get("change-shelf-from")
    if change_from_current_identifier is not None:
        current_shelf = models.Shelf.objects.get(
            user=request.user, identifier=change_from_current_identifier
        )
        handle_unshelve(book, current_shelf)

    # A book can be on multiple shelves, but only on one read status shelf at a time
    if desired_shelf.identifier in models.Shelf.READ_STATUS_IDENTIFIERS:
        current_read_status_shelfbook = (
            models.ShelfBook.objects.select_related("shelf")
            .filter(
                shelf__identifier__in=models.Shelf.READ_STATUS_IDENTIFIERS,
                user=request.user,
                book=book,
            )
            .first()
        )
        if current_read_status_shelfbook is not None:
            if (
                current_read_status_shelfbook.shelf.identifier
                != desired_shelf.identifier
            ):
                handle_unshelve(book, current_read_status_shelfbook.shelf)
            else:  # It is already on the shelf
                return redirect(request.headers.get("Referer", "/"))

        models.ShelfBook.objects.create(
            book=book, shelf=desired_shelf, user=request.user
        )
    else:
        try:
            models.ShelfBook.objects.create(
                book=book, shelf=desired_shelf, user=request.user
            )
        # The book is already on this shelf.
        # Might be good to alert, or reject the action?
        except IntegrityError:
            pass
    return redirect(request.headers.get("Referer", "/"))


@login_required
@require_POST
def unshelve(request):
    """put a  on a user's shelf"""
    book = models.Edition.objects.get(id=request.POST["book"])
    current_shelf = models.Shelf.objects.get(id=request.POST["shelf"])

    handle_unshelve(book, current_shelf)
    return redirect(request.headers.get("Referer", "/"))


def handle_unshelve(book, shelf):
    """unshelve a book"""
    row = models.ShelfBook.objects.get(book=book, shelf=shelf)
    row.delete()
