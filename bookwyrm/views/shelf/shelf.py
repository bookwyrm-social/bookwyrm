""" shelf views """
from collections import namedtuple

from django.db.models import OuterRef, Subquery, F, Max
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import View

from bookwyrm import forms, models
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.settings import PAGE_LENGTH
from bookwyrm.views.helpers import is_api_request, get_user_from_username


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
            shelves = models.Shelf.privacy_filter(request.user).filter(user=user).all()

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

        if is_api_request(request) and shelf_identifier:
            return ActivitypubResponse(shelf.to_activity(**request.GET))

        reviews = models.Review.objects
        if not is_self:
            reviews = models.Review.privacy_filter(request.user)

        reviews = reviews.filter(
            user=user,
            rating__isnull=False,
            book__id=OuterRef("id"),
            deleted=False,
        ).order_by("-published_date")

        reading = models.ReadThrough.objects

        reading = reading.filter(user=user, book__id=OuterRef("id")).order_by(
            "start_date"
        )

        books = books.annotate(shelved_date=Max("shelfbook__shelved_date"))
        books = books.annotate(
            rating=Subquery(reviews.values("rating")[:1]),
            start_date=Subquery(reading.values("start_date")[:1]),
            finish_date=Subquery(reading.values("finish_date")[:1]),
            author=Subquery(
                models.Book.objects.filter(id=OuterRef("id")).values("authors__name")[
                    :1
                ]
            ),
        ).prefetch_related("authors")

        books = sort_books(books, request.GET.get("sort"))

        paginated = Paginator(
            books,
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
            "sort": request.GET.get("sort"),
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

        # you can't change the name of the default shelves
        if not shelf.editable and request.POST.get("name") != shelf.name:
            return HttpResponseBadRequest()

        form = forms.ShelfForm(request.POST, instance=shelf)
        if not form.is_valid():
            return redirect(shelf.local_path)
        shelf = form.save(request)
        return redirect(shelf.local_path)


def sort_books(books, sort):
    """Books in shelf sorting"""
    sort_fields = [
        "title",
        "author",
        "shelved_date",
        "start_date",
        "finish_date",
        "rating",
    ]

    if sort in sort_fields:
        books = books.order_by(sort)
    elif sort and sort[1:] in sort_fields:
        books = books.order_by(F(sort[1:]).desc(nulls_last=True))
    else:
        books = books.order_by("-shelved_date")
    return books
