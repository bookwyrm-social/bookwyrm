""" the good stuff! the books! """
from datetime import datetime
import dateutil.parser
import dateutil.tz
from dateutil.parser import ParserError

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from bookwyrm import models
from .helpers import get_edition, handle_reading_status
from .shelf import handle_unshelve


# pylint: disable= no-self-use
@login_required
@require_POST
def start_reading(request, book_id):
    """ begin reading a book """
    book = get_edition(book_id)
    reading_shelf = models.Shelf.objects.filter(
        identifier=models.Shelf.READING, user=request.user
    ).first()

    # create a readthrough
    readthrough = update_readthrough(request, book=book)
    if readthrough:
        readthrough.save()

        # create a progress update if we have a page
        readthrough.create_update()

    current_status_shelfbook = (
        models.ShelfBook.objects.select_related("shelf")
        .filter(
            shelf__identifier__in=models.Shelf.READ_STATUS_IDENTIFIERS,
            user=request.user,
            book=book,
        )
        .first()
    )
    if current_status_shelfbook is not None:
        if current_status_shelfbook.shelf.identifier != models.Shelf.READING:
            handle_unshelve(book, current_status_shelfbook.shelf)
        else:  # It already was on the shelf
            return redirect(request.headers.get("Referer", "/"))

    models.ShelfBook.objects.create(book=book, shelf=reading_shelf, user=request.user)

    # post about it (if you want)
    if request.POST.get("post-status"):
        privacy = request.POST.get("privacy")
        handle_reading_status(request.user, reading_shelf, book, privacy)

    return redirect(request.headers.get("Referer", "/"))


@login_required
@require_POST
def finish_reading(request, book_id):
    """ a user completed a book, yay """
    book = get_edition(book_id)
    finished_read_shelf = models.Shelf.objects.filter(
        identifier=models.Shelf.READ_FINISHED, user=request.user
    ).first()

    # update or create a readthrough
    readthrough = update_readthrough(request, book=book)
    if readthrough:
        readthrough.save()

    current_status_shelfbook = (
        models.ShelfBook.objects.select_related("shelf")
        .filter(
            shelf__identifier__in=models.Shelf.READ_STATUS_IDENTIFIERS,
            user=request.user,
            book=book,
        )
        .first()
    )
    if current_status_shelfbook is not None:
        if current_status_shelfbook.shelf.identifier != models.Shelf.READ_FINISHED:
            handle_unshelve(book, current_status_shelfbook.shelf)
        else:  # It already was on the shelf
            return redirect(request.headers.get("Referer", "/"))

    models.ShelfBook.objects.create(
        book=book, shelf=finished_read_shelf, user=request.user
    )

    # post about it (if you want)
    if request.POST.get("post-status"):
        privacy = request.POST.get("privacy")
        handle_reading_status(request.user, finished_read_shelf, book, privacy)

    return redirect(request.headers.get("Referer", "/"))


@login_required
@require_POST
def edit_readthrough(request):
    """ can't use the form because the dates are too finnicky """
    readthrough = update_readthrough(request, create=False)
    if not readthrough:
        return HttpResponseNotFound()

    # don't let people edit other people's data
    if request.user != readthrough.user:
        return HttpResponseBadRequest()
    readthrough.save()

    # record the progress update individually
    # use default now for date field
    readthrough.create_update()

    return redirect(request.headers.get("Referer", "/"))


@login_required
@require_POST
def delete_readthrough(request):
    """ remove a readthrough """
    readthrough = get_object_or_404(models.ReadThrough, id=request.POST.get("id"))

    # don't let people edit other people's data
    if request.user != readthrough.user:
        return HttpResponseBadRequest()

    readthrough.delete()
    return redirect(request.headers.get("Referer", "/"))


@login_required
@require_POST
def create_readthrough(request):
    """ can't use the form because the dates are too finnicky """
    book = get_object_or_404(models.Edition, id=request.POST.get("book"))
    readthrough = update_readthrough(request, create=True, book=book)
    if not readthrough:
        return redirect(book.local_path)
    readthrough.save()
    return redirect(request.headers.get("Referer", "/"))


def load_date_in_user_tz_as_utc(date_str: str, user: models.User) -> datetime:
    user_tz = dateutil.tz.gettz(user.preferred_timezone)
    start_date = dateutil.parser.parse(date_str, ignoretz=True)
    return start_date.replace(tzinfo=user_tz).astimezone(dateutil.tz.UTC)


def update_readthrough(request, book=None, create=True):
    """ updates but does not save dates on a readthrough """
    try:
        read_id = request.POST.get("id")
        if not read_id:
            raise models.ReadThrough.DoesNotExist
        readthrough = models.ReadThrough.objects.get(id=read_id)
    except models.ReadThrough.DoesNotExist:
        if not create or not book:
            return None
        readthrough = models.ReadThrough(
            user=request.user,
            book=book,
        )

    start_date = request.POST.get("start_date")
    if start_date:
        try:
            readthrough.start_date = load_date_in_user_tz_as_utc(
                start_date, request.user
            )
        except ParserError:
            pass

    finish_date = request.POST.get("finish_date")
    if finish_date:
        try:
            readthrough.finish_date = load_date_in_user_tz_as_utc(
                finish_date, request.user
            )
        except ParserError:
            pass

    progress = request.POST.get("progress")
    if progress:
        try:
            progress = int(progress)
            readthrough.progress = progress
        except ValueError:
            pass

    progress_mode = request.POST.get("progress_mode")
    if progress_mode:
        try:
            progress_mode = models.ProgressMode(progress_mode)
            readthrough.progress_mode = progress_mode
        except ValueError:
            pass

    if not readthrough.start_date and not readthrough.finish_date:
        return None

    return readthrough


@login_required
@require_POST
def delete_progressupdate(request):
    """ remove a progress update """
    update = get_object_or_404(models.ProgressUpdate, id=request.POST.get("id"))

    # don't let people edit other people's data
    if request.user != update.user:
        return HttpResponseBadRequest()

    update.delete()
    return redirect(request.headers.get("Referer", "/"))
