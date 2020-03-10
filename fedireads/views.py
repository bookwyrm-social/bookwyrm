''' views for pages you can go to in the application '''
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Q
from django.http import HttpResponseNotFound
from django.shortcuts import redirect
from django.template.response import TemplateResponse

from fedireads import forms, models, books_manager, incoming
from fedireads.settings import DOMAIN


def get_user_from_username(username):
    ''' helper function to resolve a localname or a username to a user '''
    try:
        user = models.User.objects.get(localname=username)
    except models.User.DoesNotExist:
        user = models.User.objects.get(username=username)
    return user


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

    activities = models.Status.objects.order_by(
        '-created_date'
    ).select_subclasses()

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

    data = {
        'user': request.user,
        'shelves': shelves,
        'recent_books': recent_books,
        'user_books': user_books,
        'activities': activities,
        'feed_tabs': ['home', 'local', 'federated'],
        'active_tab': tab,
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


@login_required
def notifications_page(request):
    ''' list notitications '''
    notifications = request.user.notification_set.all() \
            .order_by('-created_date')
    unread = [n.id for n in notifications.filter(read=False)]
    data = {
        'notifications': notifications,
        'unread': unread,
    }
    notifications.update(read=True)
    return TemplateResponse(request, 'notifications.html', data)


def user_page(request, username):
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


def status_page(request, username, status_id):
    ''' display a particular status (and replies, etc) '''
    content = request.headers.get('Accept')
    if 'json' in content:
        # we have a json request
        return incoming.get_status(request, username, status_id)
    try:
        user = get_user_from_username(username)
        status = models.Status.objects.select_subclasses().get(id=status_id)
    except ValueError:
        return HttpResponseNotFound()

    if user != status.user:
        return HttpResponseNotFound()

    data = {
        'status': status,
    }
    return TemplateResponse(request, 'status.html', data)


@login_required
def edit_profile_page(request):
    ''' profile page for a user '''
    user = request.user

    form = forms.EditUserForm(instance=request.user)
    data = {
        'form': form,
        'user': user,
    }
    return TemplateResponse(request, 'edit_user.html', data)


def book_page(request, book_identifier, tab='friends'):
    ''' info about a book '''
    book = books_manager.get_or_create_book(book_identifier)

    if isinstance(book, models.Work):
        book_reviews = models.Review.objects.filter(
            Q(book=book) | Q(book__parent_work=book),
        )
    else:
        book_reviews = models.Review.objects.filter(book=book)

    user_reviews = book_reviews.filter(
        user=request.user,
    ).all()

    if tab == 'friends':
        reviews = book_reviews.filter(
            Q(user__followers=request.user, privacy='public') | \
                Q(user=request.user) | \
                Q(mention_users=request.user),
        )
    elif tab == 'local':
        reviews = book_reviews.filter(
            Q(privacy='public') | \
                Q(mention_users=request.user),
            user__local=True,
        )
    else:
        reviews = book_reviews.filter(
            Q(privacy='public') | \
                Q(mention_users=request.user),
        )

    try:
        shelf = models.Shelf.objects.get(user=request.user, book=book)
    except models.Shelf.DoesNotExist:
        shelf = None

    rating = reviews.aggregate(Avg('rating'))
    tags = models.Tag.objects.filter(
        book=book
    ).values(
        'book', 'name', 'identifier'
    ).distinct().all()
    user_tags = models.Tag.objects.filter(
        book=book, user=request.user
    ).all()

    review_form = forms.ReviewForm()
    tag_form = forms.TagForm()
    data = {
        'book': book,
        'shelf': shelf,
        'user_reviews': user_reviews,
        'user_rating': user_reviews.aggregate(Avg('rating')),
        'reviews': reviews.distinct(),
        'rating': rating['rating__avg'],
        'tags': tags,
        'user_tags': user_tags,
        'user_tag_names': user_tags.values_list('identifier', flat=True),
        'review_form': review_form,
        'tag_form': tag_form,
        'feed_tabs': ['friends', 'local', 'federated'],
        'active_tab': tab,
        'path': '/book/%s' % book_identifier,
    }
    return TemplateResponse(request, 'book.html', data)


def author_page(request, author_identifier):
    ''' landing page for an author '''
    try:
        author = models.Author.objects.get(books_manager_key=author_identifier)
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

