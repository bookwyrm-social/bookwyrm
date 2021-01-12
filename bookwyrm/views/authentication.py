''' class views for login/register/password management views '''
from django.contrib.auth import authenticate, login
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views import View

from bookwyrm import forms
from bookwyrm.settings import DOMAIN


class LoginView(View):
    ''' authenticate an existing user '''
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('/')
        # send user to the login page
        data = {
            'title': 'Login',
            'login_form': forms.LoginForm(),
            'register_form': forms.RegisterForm(),
        }
        return TemplateResponse(request, 'login.html', data)

    def post(self, request):
        login_form = forms.LoginForm(request.POST)

        localname = login_form.data['localname']
        username = '%s@%s' % (localname, DOMAIN)
        password = login_form.data['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            # successful login
            login(request, user)
            user.last_active_date = timezone.now()
            return redirect(request.GET.get('next', '/'))

        # login errors
        login_form.non_field_errors = 'Username or password are incorrect'
        register_form = forms.RegisterForm()
        data = {
            'login_form': login_form,
            'register_form': register_form
        }
        return TemplateResponse(request, 'login.html', data)
