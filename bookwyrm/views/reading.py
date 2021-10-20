""" the good stuff! the books! """
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import models
from .status import CreateStatus
from .helpers import get_edition, handle_reading_status, is_api_request
from .helpers import load_date_in_user_tz_as_utc


@method_decorator(login_required, name="dispatch")
# pylint: disable=no-self-use
class ReadingStatus(View):
    """consider reading a book"""

    def get(self, request, status, book_id):
        """modal page"""
        book = get_edition(book_id)
        template = {
            "want": "want.html",
            "start": "start.html",
            "finish": "finish.html",
        }.get(status)
        if not template:
            return HttpResponseNotFound()
        # redirect if we're already on this shelf
        return TemplateResponse(request, f"reading_progress/{template}", {"book": book})

    def post(self, request, status, book_id):
        """Change the state of a book by shelving it and adding reading dates"""
        identifier = {
            "want": models.Shelf.TO_READ,
            "start": models.Shelf.READING,
            "finish": models.Shelf.READ_FINISHED,
        }.get(status)
        if not identifier:
            return HttpResponseBadRequest()

        desired_shelf = get_object_or_404(
            models.Shelf, identifier=identifier, user=request.user
        )

        book = (
            models.Edition.viewer_aware_objects(request.user)
            .prefetch_related("shelfbook_set__shelf")
            .get(id=book_id)
        )

        # gets the first shelf that indicates a reading status, or None
        shelves = [
            s
            for s in book.current_shelves
            if s.shelf.identifier in models.Shelf.READ_STATUS_IDENTIFIERS
        ]
        current_status_shelfbook = shelves[0] if shelves else None

        # checking the referer prevents redirecting back to the modal page
        referer = request.headers.get("Referer", "/")
        referer = "/" if "reading-status" in referer else referer
        if current_status_shelfbook is not None:
            if current_status_shelfbook.shelf.identifier != desired_shelf.identifier:
                current_status_shelfbook.delete()
            else:  # It already was on the shelf
                return redirect(referer)

        models.ShelfBook.objects.create(
            book=book, shelf=desired_shelf, user=request.user
        )

        update_readthrough_on_shelve(
            request.user,
            book,
            desired_shelf.identifier,
            start_date=request.POST.get("start_date"),
            finish_date=request.POST.get("finish_date"),
        )

        # post about it (if you want)
        if request.POST.get("post-status"):
            # is it a comment?
            if request.POST.get("content"):
                return CreateStatus.as_view()(request, "comment")
            privacy = request.POST.get("privacy")
            handle_reading_status(request.user, desired_shelf, book, privacy)

        if is_api_request(request):
            return HttpResponse()
        return redirect(referer)


@transaction.atomic
def update_readthrough_on_shelve(
    user, annotated_book, status, start_date=None, finish_date=None
):
    """update the current readthrough for a book when it is re-shelved"""
    # there *should* only be one of current active readthrough, but it's a list
    active_readthrough = next(iter(annotated_book.active_readthroughs), None)

    # deactivate all existing active readthroughs
    for readthrough in annotated_book.active_readthroughs:
        readthrough.is_active = False
        readthrough.save()

    # if the state is want-to-read, deactivating existing readthroughs is all we need
    if status == models.Shelf.TO_READ:
        return

    # if we're starting a book, we need a fresh clean active readthrough
    if status == models.Shelf.READING or not active_readthrough:
        active_readthrough = models.ReadThrough.objects.create(
            user=user, book=annotated_book
        )
    # santiize and set dates
    active_readthrough.start_date = load_date_in_user_tz_as_utc(start_date, user)
    # if the finish date is set, the readthrough will be automatically set as inactive
    active_readthrough.finish_date = load_date_in_user_tz_as_utc(finish_date, user)

    active_readthrough.save()


@login_required
@require_POST
def delete_readthrough(request):
    """remove a readthrough"""
    readthrough = get_object_or_404(models.ReadThrough, id=request.POST.get("id"))
    readthrough.raise_not_deletable(request.user)

    readthrough.delete()
    return redirect(request.headers.get("Referer", "/"))


@login_required
@require_POST
def create_readthrough(request):
    """can't use the form because the dates are too finnicky"""
    book = get_object_or_404(models.Edition, id=request.POST.get("book"))

    start_date = load_date_in_user_tz_as_utc(
        request.POST.get("start_date"), request.user
    )
    finish_date = load_date_in_user_tz_as_utc(
        request.POST.get("finish_date"), request.user
    )
    models.ReadThrough.objects.create(
        user=request.user,
        book=book,
        start_date=start_date,
        finish_date=finish_date,
    )
    return redirect("book", book.id)


@login_required
@require_POST
def delete_progressupdate(request):
    """remove a progress update"""
    update = get_object_or_404(models.ProgressUpdate, id=request.POST.get("id"))
    update.raise_not_deletable(request.user)

    update.delete()
    return redirect(request.headers.get("Referer", "/"))
