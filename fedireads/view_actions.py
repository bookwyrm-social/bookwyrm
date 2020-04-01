''' views for actions you can take in the application '''
from io import TextIOWrapper
import re

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import redirect
from django.template.response import TemplateResponse

from fedireads import forms, models, books_manager, outgoing
from fedireads.goodreads_import import GoodreadsCsv
from fedireads.settings import DOMAIN
from fedireads.views import get_user_from_username
from fedireads.books_manager import get_or_create_book


def user_login(request):
    ''' authenticate user login '''
    if request.method == 'GET':
        return redirect('/login')

    register_form = forms.RegisterForm()
    login_form = forms.LoginForm(request.POST)
    if not login_form.is_valid():
        return TemplateResponse(
            request,
            'login.html',
            {'login_form': login_form, 'register_form': register_form}
        )

    username = login_form.data['username']
    username = '%s@%s' % (username, DOMAIN)
    password = login_form.data['password']
    user = authenticate(request, username=username, password=password)
    if user is not None:
        login(request, user)
        return redirect(request.GET.get('next', '/'))
    return TemplateResponse(
        request,
        'login.html',
        {'login_form': login_form, 'register_form': register_form}
    )


def register(request):
    ''' join the server '''
    if request.method == 'GET':
        return redirect('/login')

    form = forms.RegisterForm(request.POST)
    if not form.is_valid():
        return redirect('/register/')

    username = form.data['username']
    email = form.data['email']
    password = form.data['password']

    user = models.User.objects.create_user(username, email, password)
    login(request, user)
    return redirect('/')


@login_required
def user_logout(request):
    ''' done with this place! outa here! '''
    logout(request)
    return redirect('/')


@login_required
def edit_profile(request):
    ''' les get fancy with images '''
    if not request.method == 'POST':
        return redirect('/user/%s' % request.user.localname)

    form = forms.EditUserForm(request.POST, request.FILES)
    if not form.is_valid():
        return redirect('/')

    request.user.name = form.data['name']
    if 'avatar' in form.files:
        request.user.avatar = form.files['avatar']
    request.user.summary = form.data['summary']
    request.user.manually_approves_followers = \
        form.cleaned_data['manually_approves_followers']
    request.user.save()

    outgoing.handle_update_user(request.user)
    return redirect('/user/%s' % request.user.localname)


@login_required
def edit_book(request, book_id):
    ''' edit a book cool '''
    if not request.method == 'POST':
        return redirect('/book/%s' % request.user.localname)

    try:
        book = models.Book.objects.get(id=book_id)
    except models.Book.DoesNotExist:
        return HttpResponseNotFound()

    form = forms.BookForm(request.POST, request.FILES, instance=book)
    if not form.is_valid():
        return redirect(request.headers.get('Referer', '/'))
    form.save()

    outgoing.handle_update_book(request.user, book)
    return redirect('/book/%s' % book.fedireads_key)


@login_required
def upload_cover(request, book_id):
    ''' upload a new cover '''
    # TODO: alternate covers?
    if not request.method == 'POST':
        return redirect('/book/%s' % request.user.localname)

    try:
        book = models.Book.objects.get(id=book_id)
    except models.Book.DoesNotExist:
        return HttpResponseNotFound()

    form = forms.CoverForm(request.POST, request.FILES, instance=book)
    if not form.is_valid():
        return redirect(request.headers.get('Referer', '/'))

    book.cover = form.files['cover']
    book.sync_cover = False
    book.save()

    outgoing.handle_update_book(request.user, book)
    return redirect('/book/%s' % book.fedireads_key)


@login_required
def shelve(request):
    ''' put a  on a user's shelf '''
    book = models.Book.objects.select_subclasses().get(id=request.POST['book'])
    if isinstance(book, models.Work):
        book = book.default_edition

    desired_shelf = models.Shelf.objects.filter(
        identifier=request.POST['shelf'],
        user=request.user
    ).first()

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
    outgoing.handle_shelve(request.user, book, desired_shelf)
    return redirect('/')


@login_required
def review(request):
    ''' create a book review '''
    form = forms.ReviewForm(request.POST)
    book_identifier = request.POST.get('book')
    # TODO: better failure behavior
    if not form.is_valid():
        return redirect('/book/%s' % book_identifier)

    # TODO: validation, htmlification
    name = form.data.get('name')
    content = form.data.get('content')
    rating = form.data.get('rating')

    # throws a value error if the book is not found
    book = get_or_create_book(book_identifier)

    outgoing.handle_review(request.user, book, name, content, rating)
    return redirect('/book/%s' % book_identifier)


@login_required
def comment(request):
    ''' create a book comment '''
    form = forms.CommentForm(request.POST)
    book_identifier = request.POST.get('book')
    # TODO: better failure behavior
    if not form.is_valid():
        return redirect('/book/%s' % book_identifier)

    # TODO: validation, htmlification
    content = form.data.get('content')

    outgoing.handle_comment(request.user, book_identifier, content)
    return redirect('/book/%s' % book_identifier)


@login_required
def tag(request):
    ''' tag a book '''
    # I'm not using a form here because sometimes "name" is sent as a hidden
    # field which doesn't validate
    name = request.POST.get('name')
    book_identifier = request.POST.get('book')

    outgoing.handle_tag(request.user, book_identifier, name)
    return redirect('/book/%s' % book_identifier)


@login_required
def untag(request):
    ''' untag a book '''
    name = request.POST.get('name')
    book_identifier = request.POST.get('book')

    outgoing.handle_untag(request.user, book_identifier, name)
    return redirect('/book/%s' % book_identifier)


@login_required
def reply(request):
    ''' respond to a book review '''
    form = forms.ReplyForm(request.POST)
    # this is a bit of a formality, the form is just one text field
    if not form.is_valid():
        return redirect('/')
    parent_id = request.POST['parent']
    parent = models.Status.objects.get(id=parent_id)
    outgoing.handle_reply(request.user, parent, form.data['content'])
    return redirect('/')


@login_required
def favorite(request, status_id):
    ''' like a status '''
    status = models.Status.objects.get(id=status_id)
    outgoing.handle_favorite(request.user, status)
    return redirect(request.headers.get('Referer', '/'))


@login_required
def unfavorite(request, status_id):
    ''' like a status '''
    status = models.Status.objects.get(id=status_id)
    outgoing.handle_unfavorite(request.user, status)
    return redirect(request.headers.get('Referer', '/'))

@login_required
def boost(request, status_id):
    ''' boost a status '''
    status = models.Status.objects.get(id=status_id)
    outgoing.handle_boost(request.user, status)
    return redirect(request.headers.get('Referer', '/'))

@login_required
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
def search(request):
    ''' that search bar up top '''
    query = request.GET.get('q')
    if re.match(r'\w+@\w+.\w+', query):
        # if something looks like a username, search with webfinger
        results = [outgoing.handle_account_search(query)]
        template = 'user_results.html'
    else:
        # just send the question over to book search
        results = books_manager.search(query)
        template = 'book_results.html'

    return TemplateResponse(request, template, {'results': results})


@login_required
def clear_notifications(request):
    ''' permanently delete notification for user '''
    request.user.notification_set.filter(read=True).delete()
    return redirect('/notifications')


@login_required
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
        outgoing.handle_accept(requester, request.user, follow_request)

    return redirect('/user/%s' % request.user.localname)


@login_required
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

    outgoing.handle_reject(requester, request.user, follow_request)
    return redirect('/user/%s' % request.user.localname)


@login_required
def import_data(request):
    ''' ingest a goodreads csv '''
    form = forms.ImportForm(request.POST, request.FILES)
    if form.is_valid():
        results = []
        reviews = []
        failures = []
        for item in GoodreadsCsv(TextIOWrapper(
                request.FILES['csv_file'],
                encoding=request.encoding)):
            if item.book:
                results.append(item)
                if item.rating:
                    reviews.append(item)
            else:
                failures.append(item)

        outgoing.handle_import_books(request.user, results)
        for item in reviews:
            outgoing.handle_review(
                request.user, item.book, "", item.review, item.rating)
        return TemplateResponse(request, 'import_results.html', {
            'success_count': len(results),
            'failures': failures,
        })
    return HttpResponseBadRequest()
