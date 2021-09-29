""" shelf views """
from collections import namedtuple

from django.db import IntegrityError, transaction
from django.db.models import OuterRef, Subquery, F
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import forms, models
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.settings import PAGE_LENGTH
from .helpers import is_api_request, get_user_from_username
from .helpers import privacy_filter


# pylint: disable=no-self-use
class Shelf(View):
    """shelf page"""

    def get(self, request, username, shelf_identifier=None):
        """display a shelf"""
        user = get_user_from_username(request.user, username)

        is_self = user == request.user

        if is_self:
            shelves = user.shelf_set.all()
        else:
            shelves = privacy_filter(request.user, user.shelf_set).all()

        # get the shelf and make sure the logged in user should be able to see it
        if shelf_identifier:
            shelf = get_object_or_404(user.shelf_set, identifier=shelf_identifier)
            shelf.raise_visible_to_user(request.user)
            books = shelf.books
        else:
            # this is a constructed "all books" view, with a fake "shelf" obj
            FakeShelf = namedtuple(
                "Shelf", ("identifier", "name", "user", "books", "privacy")
            )
            books = (
                models.Edition.viewer_aware_objects(request.user)
                .filter(
                    # privacy is ensured because the shelves are already filtered above
                    shelfbook__shelf__in=shelves
                )
                .distinct()
            )
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
            rating=Subquery(reviews.values("rating")[:1]),
            shelved_date=F("shelfbook__shelved_date"),
        ).prefetch_related("authors")

        paginated = Paginator(
            books.order_by("-shelfbook__updated_date"),
            PAGE_LENGTH,
        )

        page = paginated.get_page(request.GET.get("page"))
        data = {
            "user": user,
            "is_self": is_self,
            "shelves": shelves,
            "shelf": shelf,
            "books": page,
            "edit_form": forms.ShelfForm(instance=shelf if shelf_identifier else None),
            "create_form": forms.ShelfForm(),
            "page_range": paginated.get_elided_page_range(
                page.number, on_each_side=2, on_ends=1
            ),
        }

        return TemplateResponse(request, "shelf/shelf.html", data)

    @method_decorator(login_required, name="dispatch")
    # pylint: disable=unused-argument
    def post(self, request, username, shelf_identifier):
        """edit a shelf"""
        user = get_user_from_username(request.user, username)
        shelf = get_object_or_404(user.shelf_set, identifier=shelf_identifier)
        shelf.raise_not_editable(request.user)

        # you can't change the name of the default shelves
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
    shelf.raise_not_deletable(request.user)

    shelf.delete()
    return redirect("user-shelves", request.user.localname)


@login_required
@require_POST
@transaction.atomic
def shelve(request):
    """put a book on a user's shelf"""
    book = get_object_or_404(models.Edition, id=request.POST.get("book"))
    desired_shelf = get_object_or_404(
        request.user.shelf_set, identifier=request.POST.get("shelf")
    )

    # first we need to remove from the specified shelf
    change_from_current_identifier = request.POST.get("change-shelf-from")
    if change_from_current_identifier:
        # find the shelfbook obj and delete it
        get_object_or_404(
            models.ShelfBook,
            book=book,
            user=request.user,
            shelf__identifier=change_from_current_identifier,
        ).delete()

    # A book can be on multiple shelves, but only on one read status shelf at a time
    if desired_shelf.identifier in models.Shelf.READ_STATUS_IDENTIFIERS:
        # figure out where state shelf it's currently on (if any)
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
                current_read_status_shelfbook.delete()
            else:  # It is already on the shelf
                return redirect(request.headers.get("Referer", "/"))

        # create the new shelf-book entry
        models.ShelfBook.objects.create(
            book=book, shelf=desired_shelf, user=request.user
        )
    else:
        # we're putting it on a custom shelf
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
    """put a on a user's shelf"""
    book = get_object_or_404(models.Edition, id=request.POST.get("book"))
    shelf_book = get_object_or_404(
        models.ShelfBook, book=book, shelf__id=request.POST["shelf"]
    )
    shelf_book.raise_not_deletable(request.user)

    shelf_book.delete()
    return redirect(request.headers.get("Referer", "/"))
