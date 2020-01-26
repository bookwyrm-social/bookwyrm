''' application views/pages '''
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.views.decorators.csrf import csrf_exempt
from fedireads import models

@login_required
def home(request):
    ''' user feed '''
    shelves = models.Shelf.objects.filter(user=request.user.id)
    data = {
        'user': request.user,
        'shelves': shelves,
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
    following = user.followers.filter(id=request.user.id).count() > 0
    data = {
        'user': user,
        'books': books,
        'is_self': request.user.id == user.id,
        'following': following,
    }
    return TemplateResponse(request, 'user.html', data)


@csrf_exempt
@login_required
def follow(request):
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
    followed = request.POST.get('user')
    followed = models.User.objects.get(id=followed)
    followed.followers.remove(request.user)
    return redirect('/user/%s' % followed.username)


