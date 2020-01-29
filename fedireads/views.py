''' application views/pages '''
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Q
from django.http import HttpResponseNotFound
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.views.decorators.csrf import csrf_exempt
import re

from fedireads import models, openlibrary, outgoing as api
from fedireads.settings import DOMAIN


@login_required
def home(request):
    ''' user's homepage with activity feed '''
    shelves = models.Shelf.objects.filter(user=request.user.id)
    user_books = models.Book.objects.filter(shelves__user=request.user).all()
    recent_books = models.Book.objects.order_by(
        'added_date'
        )[:10]

    following = models.User.objects.filter(
        Q(followers=request.user) | Q(id=request.user.id)
    )

    # TODO: handle post privacy
    activities = models.Activity.objects.filter(
        user__in=following,
    ).select_subclasses().order_by(
        '-created_date'
    )[:10]

    data = {
        'user': request.user,
        'shelves': shelves,
        'recent_books': recent_books,
        'user_books': user_books,
        'activities': activities,
    }
    return TemplateResponse(request, 'feed.html', data)


@csrf_exempt
def user_login(request):
    ''' authentication '''
    # send user to the login page
    if request.method == 'GET':
        return TemplateResponse(request, 'login.html')

    # authenticate user
    username = request.POST['username']
    username = '%s@%s' % (username, DOMAIN)
    password = request.POST['password']
    user = authenticate(request, username=username, password=password)
    if user is not None:
        login(request, user)
        return redirect(request.GET.get('next', '/'))
    return TemplateResponse(request, 'login.html')


@csrf_exempt
@login_required
def user_logout(request):
    ''' done with this place! outa here! '''
    logout(request)
    return redirect('/')


@csrf_exempt
def register(request):
    ''' join the server '''
    if request.method == 'GET':
        return TemplateResponse(request, 'register.html')

    username = request.POST['username']
    password = request.POST['password']
    email = request.POST['email']
    password = request.POST['password']

    user = models.User.objects.create_user(username, email, password)
    login(request, user)
    return redirect('/')


@login_required
def user_profile(request, username):
    ''' profile page for a user '''
    try:
        user = models.User.objects.get(localname=username)
    except models.User.DoesNotExist:
        try:
            user = models.User.objects.get(username=username)
        except models.User.DoesNotExist:
            return HttpResponseNotFound()

    books = models.Book.objects.filter(shelves__user=user)
    data = {
        'user': user,
        'books': books,
        'is_self': request.user.id == user.id,
    }
    return TemplateResponse(request, 'user.html', data)


@login_required
def user_profile_edit(request, username):
    ''' profile page for a user '''
    try:
        user = models.User.objects.get(localname=username)
    except models.User.DoesNotExist:
        return HttpResponseNotFound()

    data = {
        'user': user,
    }
    return TemplateResponse(request, 'edit_user.html', data)


@csrf_exempt
@login_required
def upload_avatar(request):
    ''' les get fancy with images '''
    if not request.method == 'POST':
        return redirect('/')
    request.user.avatar = request.FILES['avatar']
    request.user.save()
    return redirect('/user/%s' % request.user.localname)


@login_required
def book_page(request, book_identifier):
    ''' info about a book '''
    book = openlibrary.get_or_create_book('/book/' + book_identifier)
    reviews = models.Review.objects.filter(
        Q(work=book.works.first()) | Q(book=book)
    )
    rating = reviews.aggregate(Avg('rating'))
    data = {
        'book': book,
        'reviews': reviews,
        'rating': rating['rating__avg'],
    }
    return TemplateResponse(request, 'book.html', data)


@csrf_exempt
@login_required
def shelve(request, shelf_id, book_id):
    ''' put a book on a user's shelf '''
    # TODO: handle "reshelving"
    book = models.Book.objects.get(id=book_id)
    shelf = models.Shelf.objects.get(identifier=shelf_id)
    api.handle_shelve(request.user, book, shelf)
    return redirect('/')


@csrf_exempt
@login_required
def review(request):
    ''' create a book review note '''
    # TODO: error handling
    book_identifier = request.POST.get('book')
    book = openlibrary.get_or_create_book(book_identifier)

    # TODO: validation, htmlification
    name = request.POST.get('name')
    content = request.POST.get('content')
    rating = request.POST.get('rating')

    api.handle_review(request.user, book, name, content, rating)
    return redirect(book_identifier)


@csrf_exempt
@login_required
def follow(request):
    ''' follow another user, here or abroad '''
    to_follow = request.POST.get('user')
    # should this be an actor rather than an id? idk
    to_follow = models.User.objects.get(id=to_follow)

    api.handle_outgoing_follow(request.user, to_follow)
    return redirect('/user/%s' % to_follow.username)


@csrf_exempt
@login_required
def unfollow(request):
    ''' unfollow a user '''
    # TODO: this is not an implementation!!
    followed = request.POST.get('user')
    followed = models.User.objects.get(id=followed)
    followed.followers.remove(request.user)
    return redirect('/user/%s' % followed.username)


@csrf_exempt
@login_required
def search(request):
    ''' that search bar up top '''
    query = request.GET.get('q')
    if re.match(r'\w+@\w+.\w+', query):
        results = [api.handle_account_search(query)]
    else:
        # TODO: book search
        results = []

    return TemplateResponse(request, 'results.html', {'results': results})

