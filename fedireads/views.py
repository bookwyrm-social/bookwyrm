''' application views/pages '''
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Q
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import redirect
from django.template.response import TemplateResponse
import re

from fedireads import forms, models, openlibrary, outgoing, incoming
from fedireads.settings import DOMAIN


@login_required
def home(request):
    ''' this is the same as the feed on the home tab '''
    return home_tab(request, 'home')


@login_required
def home_tab(request, tab):
    ''' user's homepage with activity feed '''
    shelves = []
    for identifier in ['reading', 'to-read']:
        shelf = models.Shelf.objects.get(
            user=request.user,
            identifier=identifier,
        )
        if not shelf.books.count():
            continue
        shelves.append({
            'name': shelf.name,
            'identifier': shelf.identifier,
            'books': shelf.books.all()[:3],
            'size': shelf.books.count(),
        })

    # allows us to check if a user has shelved a book
    user_books = models.Book.objects.filter(shelves__user=request.user).all()

    # books new to the instance, for discovery
    recent_books = models.Book.objects.order_by(
        '-created_date'
    )[:5]

    # status updates for your follow network
    following = models.User.objects.filter(
        Q(followers=request.user) | Q(id=request.user.id)
    )

    activities = models.Status.objects.select_subclasses().order_by(
        '-created_date'
    )

    if tab == 'home':
        # people you follow and direct mentions
        activities = activities.filter(
            Q(user__in=following, privacy='public') | \
                Q(mention_users=request.user)
        )
    elif tab == 'local':
        # everyone on this instance
        activities = activities.filter(user__local=True, privacy='public')
    else:
        # all activities from everyone you federate with
        activities = activities.filter(privacy='public')

    activities = activities[:10]

    comment_form = forms.CommentForm()
    data = {
        'user': request.user,
        'shelves': shelves,
        'recent_books': recent_books,
        'user_books': user_books,
        'activities': activities,
        'feed_tabs': ['home', 'local', 'federated'],
        'active_tab': tab,
        'comment_form': comment_form,
    }
    return TemplateResponse(request, 'feed.html', data)


def user_login(request):
    ''' authentication '''
    # send user to the login page
    if request.method == 'GET':
        form = forms.LoginForm()
        return TemplateResponse(request, 'login.html', {'login_form': form})

    # authenticate user
    form = forms.LoginForm(request.POST)
    if not form.is_valid():
        return TemplateResponse(request, 'login.html', {'login_form': form})

    username = form.data['username']
    username = '%s@%s' % (username, DOMAIN)
    password = form.data['password']
    user = authenticate(request, username=username, password=password)
    if user is not None:
        login(request, user)
        return redirect(request.GET.get('next', '/'))
    return TemplateResponse(request, 'login.html', {'login_form': form})


@login_required
def user_logout(request):
    ''' done with this place! outa here! '''
    logout(request)
    return redirect('/')


def register(request):
    ''' join the server '''
    if request.method == 'GET':
        form = forms.RegisterForm()
        return TemplateResponse(
            request,
            'register.html',
            {'register_form': form}
        )

    form = forms.RegisterForm(request.POST)
    if not form.is_valid():
        return redirect('/register/')

    username = form.data['username']
    email = form.data['email']
    password = form.data['password']

    user = models.User.objects.create_user(username, email, password)
    login(request, user)
    return redirect('/')


def user_profile(request, username):
    ''' profile page for a user '''
    content = request.headers.get('Accept')
    # TODO: this should probably be the full content type? maybe?
    if 'json' in content:
        # we have a json request
        return incoming.get_actor(request, username)

    # otherwise we're at a UI view
    try:
        user = get_user_from_username(username)
    except models.User.DoesNotExist:
        return HttpResponseNotFound()

    # TODO: change display with privacy and authentication considerations
    shelves = models.Shelf.objects.filter(user=user)
    ratings = {r.book.id: r.rating for r in \
            models.Review.objects.filter(user=user, book__shelves__user=user)}

    data = {
        'user': user,
        'shelves': shelves,
        'ratings': ratings,
        'is_self': request.user.id == user.id,
    }
    return TemplateResponse(request, 'user.html', data)

def get_user_from_username(username):
    ''' resolve a localname or a username to a user '''
    try:
        user = models.User.objects.get(localname=username)
    except models.User.DoesNotExist:
        user = models.User.objects.get(username=username)
    return user


@login_required
def user_profile_edit(request, username):
    ''' profile page for a user '''
    try:
        user = models.User.objects.get(localname=username)
    except models.User.DoesNotExist:
        return HttpResponseNotFound()

    form = forms.EditUserForm(instance=request.user)
    data = {
        'form': form,
        'user': user,
    }
    return TemplateResponse(request, 'edit_user.html', data)


# TODO: there oughta be clear naming between endpoints and pages
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
    request.user.save()
    return redirect('/user/%s' % request.user.localname)


@login_required
def book_page(request, book_identifier):
    ''' info about a book '''
    book = openlibrary.get_or_create_book(book_identifier)
    # TODO: again, post privacy?
    reviews = models.Review.objects.filter(book=book)
    rating = reviews.aggregate(Avg('rating'))
    tags = models.Tag.objects.filter(
        book=book
    ).values(
        'book', 'name', 'identifier'
    ).distinct().all()
    user_tags = models.Tag.objects.filter(
        book=book, user=request.user
    ).values_list('name', flat=True)

    review_form = forms.ReviewForm()
    tag_form = forms.TagForm()
    data = {
        'book': book,
        'reviews': reviews,
        'rating': rating['rating__avg'],
        'tags': tags,
        'user_tags': user_tags,
        'review_form': review_form,
        'tag_form': tag_form,
    }
    return TemplateResponse(request, 'book.html', data)


@login_required
def author_page(request, author_identifier):
    ''' landing page for an author '''
    try:
        author = models.Author.objects.get(openlibrary_key=author_identifier)
    except ValueError:
        return HttpResponseNotFound()

    books = models.Book.objects.filter(authors=author)
    data = {
        'author': author,
        'books': books,
    }
    return TemplateResponse(request, 'author.html', data)


def tag_page(request, tag_id):
    ''' books related to a tag '''
    tag_obj = models.Tag.objects.filter(identifier=tag_id).first()
    books = models.Book.objects.filter(tag__identifier=tag_id).distinct()
    data = {
        'books': books,
        'tag': tag_obj,
    }
    return TemplateResponse(request, 'tag.html', data)


def shelf_page(request, username, shelf_identifier):
    ''' display a shelf '''
    # TODO: json view
    try:
        user = get_user_from_username(username)
    except models.User.DoesNotExist:
        return HttpResponseNotFound()

    shelf = models.Shelf.objects.get(user=user, identifier=shelf_identifier)
    data = {
        'shelf': shelf,
        'user': user,
    }
    return TemplateResponse(request, 'shelf.html', data)


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
        # just send the question over to openlibrary for book search
        results = openlibrary.book_search(query)
        template = 'book_results.html'

    return TemplateResponse(request, template, {'results': results})

