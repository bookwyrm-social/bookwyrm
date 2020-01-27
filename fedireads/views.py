''' application views/pages '''
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.db.models import FilteredRelation, Q
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.views.decorators.csrf import csrf_exempt
from fedireads import models
import fedireads.activitypub_templates as templates
from fedireads.federation import broadcast_activity, broadcast_follow

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
    models.ShelfBook(book=book, shelf=shelf, added_by=request.user).save()

    # send out the activitypub action
    summary = '%s marked %s as %s' % (
        request.user.username,
        book.data['title'],
        shelf.name
    )

    obj = templates.note_object(request.user, summary)
    #activity = templates.shelve_activity(request.user, book, shelf)
    recipients = [templates.inbox(u) for u in request.user.followers.all()]
    broadcast_activity(request.user, obj, recipients)

    return redirect('/')


@csrf_exempt
@login_required
def follow(request):
    ''' follow another user, here or abroad '''
    to_follow = request.POST.get('user')
    to_follow = models.User.objects.get(id=to_follow)

    activity = templates.follow_request(request.user, to_follow.actor)
    broadcast_follow(request.user, activity, templates.inbox(to_follow))
    return redirect('/user/%s' % to_follow.username)



@csrf_exempt
@login_required
def unfollow(request):
    ''' unfollow a user '''
    followed = request.POST.get('user')
    followed = models.User.objects.get(id=followed)
    followed.followers.remove(request.user)
    return redirect('/user/%s' % followed.username)

