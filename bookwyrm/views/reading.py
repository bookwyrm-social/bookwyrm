""" the good stuff! the books! """
from datetime import datetime
import dateutil.parser
import dateutil.tz
from dateutil.parser import ParserError

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import models
from .helpers import get_edition, handle_reading_status


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
        return TemplateResponse(request, f"reading_progress/{template}", {"book": book})

    def post(self, request, status, book_id):
        """desire a book"""
        identifier = {
            "want": models.Shelf.TO_READ,
            "start": models.Shelf.READING,
            "finish": models.Shelf.READ_FINISHED,
        }.get(status)
        if not identifier:
            return HttpResponseBadRequest()

        desired_shelf = models.Shelf.objects.filter(
            identifier=identifier, user=request.user
        ).first()

        book = get_edition(book_id)

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
            if current_status_shelfbook.shelf.identifier != desired_shelf.identifier:
                current_status_shelfbook.delete()
            else:  # It already was on the shelf
                return redirect(request.headers.get("Referer", "/"))

        models.ShelfBook.objects.create(
            book=book, shelf=desired_shelf, user=request.user
        )

        if desired_shelf.identifier != models.Shelf.TO_READ:
            # update or create a readthrough
            readthrough = update_readthrough(request, book=book)
            if readthrough:
                readthrough.save()

        # post about it (if you want)
        if request.POST.get("post-status"):
            privacy = request.POST.get("privacy")
            handle_reading_status(request.user, desired_shelf, book, privacy)

        return redirect(request.headers.get("Referer", "/"))


@login_required
@require_POST
def edit_readthrough(request):
    """can't use the form because the dates are too finnicky"""
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
    """remove a readthrough"""
    readthrough = get_object_or_404(models.ReadThrough, id=request.POST.get("id"))

    # don't let people edit other people's data
    if request.user != readthrough.user:
        return HttpResponseBadRequest()

    readthrough.delete()
    return redirect(request.headers.get("Referer", "/"))


@login_required
@require_POST
def create_readthrough(request):
    """can't use the form because the dates are too finnicky"""
    book = get_object_or_404(models.Edition, id=request.POST.get("book"))
    readthrough = update_readthrough(request, create=True, book=book)
    if not readthrough:
        return redirect(book.local_path)
    readthrough.save()
    return redirect(request.headers.get("Referer", "/"))


def load_date_in_user_tz_as_utc(date_str: str, user: models.User) -> datetime:
    """ensures that data is stored consistently in the UTC timezone"""
    user_tz = dateutil.tz.gettz(user.preferred_timezone)
    start_date = dateutil.parser.parse(date_str, ignoretz=True)
    return start_date.replace(tzinfo=user_tz).astimezone(dateutil.tz.UTC)


def update_readthrough(request, book=None, create=True):
    """updates but does not save dates on a readthrough"""
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
    """remove a progress update"""
    update = get_object_or_404(models.ProgressUpdate, id=request.POST.get("id"))

    # don't let people edit other people's data
    if request.user != update.user:
        return HttpResponseBadRequest()

    update.delete()
    return redirect(request.headers.get("Referer", "/"))
