''' application views/pages '''
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.views.decorators.csrf import csrf_exempt
from fedireads.models import Shelf

@login_required
def home(request):
    ''' user feed '''
    shelves = Shelf.objects.filter(user=request.user.id)
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
    logout(request)
    return redirect('/')
