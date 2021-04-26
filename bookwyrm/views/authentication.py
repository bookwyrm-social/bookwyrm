""" class views for login/register views """
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View

from bookwyrm import forms, models
from bookwyrm.settings import DOMAIN


# pylint: disable= no-self-use
@method_decorator(csrf_exempt, name="dispatch")
class Login(View):
    """authenticate an existing user"""

    def get(self, request):
        """login page"""
        if request.user.is_authenticated:
            return redirect("/")
        # sene user to the login page
        data = {
            "login_form": forms.LoginForm(),
            "register_form": forms.RegisterForm(),
        }
        return TemplateResponse(request, "login.html", data)

    def post(self, request):
        """authentication action"""
        if request.user.is_authenticated:
            return redirect("/")
        login_form = forms.LoginForm(request.POST)

        localname = login_form.data["localname"]
        if "@" in localname:  # looks like an email address to me
            email = localname
            try:
                username = models.User.objects.get(email=email)
            except models.User.DoesNotExist:  # maybe it's a full username?
                username = localname
        else:
            username = "%s@%s" % (localname, DOMAIN)
        password = login_form.data["password"]
        user = authenticate(request, username=username, password=password)
        if user is not None:
            # successful login
            login(request, user)
            user.last_active_date = timezone.now()
            user.save(broadcast=False)
            return redirect(request.GET.get("next", "/"))

        # login errors
        login_form.non_field_errors = "Username or password are incorrect"
        register_form = forms.RegisterForm()
        data = {"login_form": login_form, "register_form": register_form}
        return TemplateResponse(request, "login.html", data)


class Register(View):
    """register a user"""

    def post(self, request):
        """join the server"""
        if not models.SiteSettings.get().allow_registration:
            invite_code = request.POST.get("invite_code")

            if not invite_code:
                raise PermissionDenied

            invite = get_object_or_404(models.SiteInvite, code=invite_code)
            if not invite.valid():
                raise PermissionDenied
        else:
            invite = None

        form = forms.RegisterForm(request.POST)
        errors = False
        if not form.is_valid():
            errors = True

        localname = form.data["localname"].strip()
        email = form.data["email"]
        password = form.data["password"]

        # check localname and email uniqueness
        if models.User.objects.filter(localname=localname).first():
            form.errors["localname"] = ["User with this username already exists"]
            errors = True

        if errors:
            data = {
                "login_form": forms.LoginForm(),
                "register_form": form,
                "invite": invite,
                "valid": invite.valid() if invite else True,
            }
            if invite:
                return TemplateResponse(request, "invite.html", data)
            return TemplateResponse(request, "login.html", data)

        username = "%s@%s" % (localname, DOMAIN)
        user = models.User.objects.create_user(
            username, email, password, localname=localname, local=True
        )
        if invite:
            invite.times_used += 1
            invite.invitees.add(user)
            invite.save()

        login(request, user)
        return redirect("get-started-profile")


@method_decorator(login_required, name="dispatch")
class Logout(View):
    """log out"""

    def get(self, request):
        """done with this place! outa here!"""
        logout(request)
        return redirect("/")
