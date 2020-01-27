''' application views/pages '''
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.db.models import FilteredRelation, Q
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.views.decorators.csrf import csrf_exempt
from fedireads import models
import fedireads.activitypub_templates as templates
from fedireads.federation import broadcast_action

@login_required
def home(request):
    ''' user feed '''
    shelves = models.Shelf.objects.filter(user=request.user.id)
    recent_books = models.Book.objects.order_by(
        'added_date'
    ).annotate(
        user_shelves=FilteredRelation(
            'shelves',
            condition=Q(shelves__user_id=request.user.id)
        )
    ).values('id', 'authors', 'data', 'user_shelves')
    data = {
        'user': request.user,
        'shelves': shelves,
        'recent_books': recent_books,
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


@login_required
def user_profile(request, username):
    ''' profile page for a user '''
    user = models.User.objects.get(username=username)
    books = models.Book.objects.filter(shelves__user=user)
    data = {
        'user': user,
        'books': books,
        'is_self': request.user.id == user.id,
    }
    return TemplateResponse(request, 'user.html', data)


@csrf_exempt
@login_required
def shelve(request, shelf_id, book_id):
    ''' put a book on a user's shelf '''
    book = models.Book.objects.get(id=book_id)
    shelf = models.Shelf.objects.get(identifier=shelf_id)

    # update the database
    #models.ShelfBook(book=book, shelf=shelf, added_by=request.user).save()

    # send out the activitypub action
    action = templates.shelve_action(request.user, book, shelf)
    recipients = [u.actor['inbox'] for u in request.user.followers.all()]
    broadcast_action(request.user, action, recipients)

    return redirect('/')


@csrf_exempt
@login_required
def follow(request):
    ''' follow another user, here or abroad '''
    followed = request.POST.get('user')
    followed = models.User.objects.get(id=followed)
    followed.followers.add(request.user)
    activity = {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'summary': '',
        'type': 'Follow',
        'actor': {
            'type': 'Person',
            'name': request.user.get_actor(),
        },
        'object': {
            'type': 'Person',
            'name': followed.get_actor(),
        }
    }

    models.Activity(
        data=activity,
        user=request.user,
    )

    return redirect('/user/%s' % followed.username)


@csrf_exempt
@login_required
def unfollow(request):
    ''' unfollow a user '''
    followed = request.POST.get('user')
    followed = models.User.objects.get(id=followed)
    followed.followers.remove(request.user)
    return redirect('/user/%s' % followed.username)

