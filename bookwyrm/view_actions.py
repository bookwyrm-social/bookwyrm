''' views for actions you can take in the application '''
import dateutil.parser
from dateutil.parser import ParserError

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from bookwyrm import models, outgoing

def get_edition(book_id):
    ''' look up a book in the db and return an edition '''
    book = models.Book.objects.select_subclasses().get(id=book_id)
    if isinstance(book, models.Work):
        book = book.get_default_edition()
    return book

def get_user_from_username(username):
    ''' helper function to resolve a localname or a username to a user '''
    # raises DoesNotExist if user is now found
    try:
        return models.User.objects.get(localname=username)
    except models.User.DoesNotExist:
        return models.User.objects.get(username=username)


@login_required
@require_POST
def start_reading(request, book_id):
    ''' begin reading a book '''
    book = get_edition(book_id)
    shelf = models.Shelf.objects.filter(
        identifier='reading',
        user=request.user
    ).first()

    # create a readthrough
    readthrough = update_readthrough(request, book=book)
    if readthrough.start_date:
        readthrough.save()

    # shelve the book
    if request.POST.get('reshelve', True):
        try:
            current_shelf = models.Shelf.objects.get(
                user=request.user,
                edition=book
            )
            outgoing.handle_unshelve(request.user, book, current_shelf)
        except models.Shelf.DoesNotExist:
            # this just means it isn't currently on the user's shelves
            pass
    outgoing.handle_shelve(request.user, book, shelf)

    # post about it (if you want)
    if request.POST.get('post-status'):
        privacy = request.POST.get('privacy')
        outgoing.handle_reading_status(request.user, shelf, book, privacy)

    return redirect(request.headers.get('Referer', '/'))


@login_required
@require_POST
def finish_reading(request, book_id):
    ''' a user completed a book, yay '''
    book = get_edition(book_id)
    shelf = models.Shelf.objects.filter(
        identifier='read',
        user=request.user
    ).first()

    # update or create a readthrough
    readthrough = update_readthrough(request, book=book)
    if readthrough.start_date or readthrough.finish_date:
        readthrough.save()

    # shelve the book
    if request.POST.get('reshelve', True):
        try:
            current_shelf = models.Shelf.objects.get(
                user=request.user,
                edition=book
            )
            outgoing.handle_unshelve(request.user, book, current_shelf)
        except models.Shelf.DoesNotExist:
            # this just means it isn't currently on the user's shelves
            pass
    outgoing.handle_shelve(request.user, book, shelf)

    # post about it (if you want)
    if request.POST.get('post-status'):
        privacy = request.POST.get('privacy')
        outgoing.handle_reading_status(request.user, shelf, book, privacy)

    return redirect(request.headers.get('Referer', '/'))


@login_required
@require_POST
def edit_readthrough(request):
    ''' can't use the form because the dates are too finnicky '''
    readthrough = update_readthrough(request, create=False)
    if not readthrough:
        return HttpResponseNotFound()

    # don't let people edit other people's data
    if request.user != readthrough.user:
        return HttpResponseBadRequest()
    readthrough.save()

    return redirect(request.headers.get('Referer', '/'))


@login_required
@require_POST
def delete_readthrough(request):
    ''' remove a readthrough '''
    readthrough = get_object_or_404(
        models.ReadThrough, id=request.POST.get('id'))

    # don't let people edit other people's data
    if request.user != readthrough.user:
        return HttpResponseBadRequest()

    readthrough.delete()
    return redirect(request.headers.get('Referer', '/'))


@login_required
@require_POST
def create_readthrough(request):
    ''' can't use the form because the dates are too finnicky '''
    book = get_object_or_404(models.Edition, id=request.POST.get('book'))
    readthrough = update_readthrough(request, create=True, book=book)
    if not readthrough:
        return redirect(book.local_path)
    readthrough.save()
    return redirect(request.headers.get('Referer', '/'))


@login_required
@require_POST
def follow(request):
    ''' follow another user, here or abroad '''
    username = request.POST['user']
    try:
        to_follow = get_user_from_username(username)
    except models.User.DoesNotExist:
        return HttpResponseBadRequest()

    outgoing.handle_follow(request.user, to_follow)
    user_slug = to_follow.localname if to_follow.localname \
        else to_follow.username
    return redirect('/user/%s' % user_slug)


@login_required
@require_POST
def unfollow(request):
    ''' unfollow a user '''
    username = request.POST['user']
    try:
        to_unfollow = get_user_from_username(username)
    except models.User.DoesNotExist:
        return HttpResponseBadRequest()

    outgoing.handle_unfollow(request.user, to_unfollow)
    user_slug = to_unfollow.localname if to_unfollow.localname \
        else to_unfollow.username
    return redirect('/user/%s' % user_slug)


@login_required
@require_POST
def accept_follow_request(request):
    ''' a user accepts a follow request '''
    username = request.POST['user']
    try:
        requester = get_user_from_username(username)
    except models.User.DoesNotExist:
        return HttpResponseBadRequest()

    try:
        follow_request = models.UserFollowRequest.objects.get(
            user_subject=requester,
            user_object=request.user
        )
    except models.UserFollowRequest.DoesNotExist:
        # Request already dealt with.
        pass
    else:
        outgoing.handle_accept(follow_request)

    return redirect('/user/%s' % request.user.localname)


@login_required
@require_POST
def delete_follow_request(request):
    ''' a user rejects a follow request '''
    username = request.POST['user']
    try:
        requester = get_user_from_username(username)
    except models.User.DoesNotExist:
        return HttpResponseBadRequest()

    try:
        follow_request = models.UserFollowRequest.objects.get(
            user_subject=requester,
            user_object=request.user
        )
    except models.UserFollowRequest.DoesNotExist:
        return HttpResponseBadRequest()

    outgoing.handle_reject(follow_request)
    return redirect('/user/%s' % request.user.localname)


def update_readthrough(request, book=None, create=True):
    ''' updates but does not save dates on a readthrough '''
    try:
        read_id = request.POST.get('id')
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

    start_date = request.POST.get('start_date')
    if start_date:
        try:
            start_date = timezone.make_aware(dateutil.parser.parse(start_date))
            readthrough.start_date = start_date
        except ParserError:
            pass

    finish_date = request.POST.get('finish_date')
    if finish_date:
        try:
            finish_date = timezone.make_aware(
                dateutil.parser.parse(finish_date))
            readthrough.finish_date = finish_date
        except ParserError:
            pass

    if not readthrough.start_date and not readthrough.finish_date:
        return None

    return readthrough
