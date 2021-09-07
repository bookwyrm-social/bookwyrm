""" class views for login/register views """
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_variables, sensitive_post_parameters

from bookwyrm import forms, models
from bookwyrm.settings import DOMAIN


# pylint: disable=no-self-use
@method_decorator(csrf_exempt, name="dispatch")
class Login(View):
    """authenticate an existing user"""

    def get(self, request, confirmed=None):
        """login page"""
        if request.user.is_authenticated:
            return redirect("/")
        # send user to the login page
        data = {
            "show_confirmed_email": confirmed,
            "login_form": forms.LoginForm(),
            "register_form": forms.RegisterForm(),
        }
        return TemplateResponse(request, "login.html", data)

    @sensitive_variables("password")
    @method_decorator(sensitive_post_parameters("password"))
    def post(self, request):
        """authentication action"""
        if request.user.is_authenticated:
            return redirect("/")
        login_form = forms.LoginForm(request.POST)

        localname = login_form.data["localname"]
        if "@" in localname:  # looks like an email address to me
            try:
                username = models.User.objects.get(email=localname).username
            except models.User.DoesNotExist:  # maybe it's a full username?
                username = localname
        else:
            username = "%s@%s" % (localname, DOMAIN)
        password = login_form.data["password"]

        # perform authentication
        user = authenticate(request, username=username, password=password)
        if user is not None:
            # successful login
            login(request, user)
            user.last_active_date = timezone.now()
            user.save(broadcast=False, update_fields=["last_active_date"])
            if request.POST.get("first_login"):
                return redirect("get-started-profile")
            return redirect(request.GET.get("next", "/"))

        # maybe the user is pending email confirmation
        if models.User.objects.filter(
            username=username, is_active=False, deactivation_reason="pending"
        ).exists():
            return redirect("confirm-email")

        # login errors
        login_form.non_field_errors = _("Username or password are incorrect")
        register_form = forms.RegisterForm()
        data = {"login_form": login_form, "register_form": register_form}
        return TemplateResponse(request, "login.html", data)


@method_decorator(login_required, name="dispatch")
class Logout(View):
    """log out"""

    def get(self, request):
        """done with this place! outa here!"""
        logout(request)
        return redirect("/")
