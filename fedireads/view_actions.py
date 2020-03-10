''' views for actions you can take in the application '''
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.template.response import TemplateResponse
import re

from fedireads import forms, models, books_manager, outgoing
from fedireads.views import get_user_from_username


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
    request.user.manually_approves_followers = form.cleaned_data['manually_approves_followers']
    request.user.save()
    return redirect('/user/%s' % request.user.localname)


@login_required
def shelve(request):
    ''' put a book on a user's shelf '''
    book = models.Book.objects.get(id=request.POST['book'])
    desired_shelf = models.Shelf.objects.filter(
        identifier=request.POST['shelf'],
        user=request.user
    ).first()

    if request.POST.get('reshelve', True):
        try:
            current_shelf = models.Shelf.objects.get(
                user=request.user,
                book=book
            )
            outgoing.handle_unshelve(request.user, book, current_shelf)
        except models.Shelf.DoesNotExist:
            # this just means it isn't currently on the user's shelves
            pass
    outgoing.handle_shelve(request.user, book, desired_shelf)
    return redirect('/')


@login_required
def review(request):
    ''' create a book review note '''
    form = forms.ReviewForm(request.POST)
    book_identifier = request.POST.get('book')
    # TODO: better failure behavior
    if not form.is_valid():
        return redirect('/book/%s' % book_identifier)

    # TODO: validation, htmlification
    name = form.data.get('name')
    content = form.data.get('content')
    rating = int(form.data.get('rating'))

    outgoing.handle_review(request.user, book_identifier, name, content, rating)
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
def comment(request):
    ''' respond to a book review '''
    form = forms.CommentForm(request.POST)
    # this is a bit of a formality, the form is just one text field
    if not form.is_valid():
        return redirect('/')
    parent_id = request.POST['parent']
    parent = models.Status.objects.get(id=parent_id)
    outgoing.handle_comment(request.user, parent, form.data['content'])
    return redirect('/')


@login_required
def favorite(request, status_id):
    ''' like a status '''
    status = models.Status.objects.get(id=status_id)
    outgoing.handle_outgoing_favorite(request.user, status)
    return redirect(request.headers.get('Referer', '/'))


@login_required
def follow(request):
    ''' follow another user, here or abroad '''
    username = request.POST['user']
    try:
        to_follow = get_user_from_username(username)
    except models.User.DoesNotExist:
        return HttpResponseBadRequest()

    outgoing.handle_outgoing_follow(request.user, to_follow)
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

    outgoing.handle_outgoing_unfollow(request.user, to_unfollow)
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
    request.user.notification_set.filter(read=True).delete()
    return redirect('/notifications')

