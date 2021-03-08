""" the good stuff! the books! """
import dateutil.parser
from dateutil.parser import ParserError

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
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
    shelf = models.Shelf.objects.filter(identifier="reading", user=request.user).first()

    # create a readthrough
    readthrough = update_readthrough(request, book=book)
    if readthrough:
        readthrough.save()

        # create a progress update if we have a page
        readthrough.create_update()

    # shelve the book
    if request.POST.get("reshelve", True):
        try:
            current_shelf = models.Shelf.objects.get(user=request.user, edition=book)
            handle_unshelve(request.user, book, current_shelf)
        except models.Shelf.DoesNotExist:
            # this just means it isn't currently on the user's shelves
            pass
    models.ShelfBook.objects.create(book=book, shelf=shelf, user=request.user)

    # post about it (if you want)
    if request.POST.get("post-status"):
        privacy = request.POST.get("privacy")
        handle_reading_status(request.user, shelf, book, privacy)

    return redirect(request.headers.get("Referer", "/"))


@login_required
@require_POST
def finish_reading(request, book_id):
    """ a user completed a book, yay """
    book = get_edition(book_id)
    shelf = models.Shelf.objects.filter(identifier="read", user=request.user).first()

    # update or create a readthrough
    readthrough = update_readthrough(request, book=book)
    if readthrough:
        readthrough.save()

    # shelve the book
    if request.POST.get("reshelve", True):
        try:
            current_shelf = models.Shelf.objects.get(user=request.user, edition=book)
            handle_unshelve(request.user, book, current_shelf)
        except models.Shelf.DoesNotExist:
            # this just means it isn't currently on the user's shelves
            pass
    models.ShelfBook.objects.create(book=book, shelf=shelf, user=request.user)

    # post about it (if you want)
    if request.POST.get("post-status"):
        privacy = request.POST.get("privacy")
        handle_reading_status(request.user, shelf, book, privacy)

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
            start_date = timezone.make_aware(dateutil.parser.parse(start_date))
            readthrough.start_date = start_date
        except ParserError:
            pass

    finish_date = request.POST.get("finish_date")
    if finish_date:
        try:
            finish_date = timezone.make_aware(dateutil.parser.parse(finish_date))
            readthrough.finish_date = finish_date
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
