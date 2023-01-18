""" shelf views """
from django.db import IntegrityError, transaction
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from bookwyrm.utils.validate import validate_url_domain

from bookwyrm import forms, models


@login_required
@require_POST
def create_shelf(request):
    """user generated shelves"""
    form = forms.ShelfForm(request.POST)
    if not form.is_valid():
        return redirect("user-shelves", request.user.localname)

    shelf = form.save(request)
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
    next_step = request.META.get("HTTP_REFERER")
    next_step = validate_url_domain(next_step, "/")
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
            # If it is not already on the shelf
            if (
                current_read_status_shelfbook.shelf.identifier
                != desired_shelf.identifier
            ):
                current_read_status_shelfbook.delete()
            else:
                return redirect(next_step)

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

    return redirect(next_step)


@login_required
@require_POST
def unshelve(request, book_id=False):
    """remove a book from a user's shelf"""
    next_step = request.META.get("HTTP_REFERER")
    next_step = validate_url_domain(next_step, "/")
    identity = book_id if book_id else request.POST.get("book")
    book = get_object_or_404(models.Edition, id=identity)
    shelf_book = get_object_or_404(
        models.ShelfBook, book=book, shelf__id=request.POST["shelf"]
    )
    shelf_book.raise_not_deletable(request.user)
    shelf_book.delete()
    return redirect(next_step)
