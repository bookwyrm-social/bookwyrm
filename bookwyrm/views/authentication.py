""" class views for login/register views """
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views import View

from bookwyrm import emailing, forms, models
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
        login_form.non_field_errors = "Username or password are incorrect"
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


class Register(View):
    """register a user"""

    def post(self, request):
        """join the server"""
        settings = models.SiteSettings.get()
        if not settings.allow_registration:
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
            username,
            email,
            password,
            localname=localname,
            local=True,
            deactivation_reason="pending" if settings.require_confirm_email else None,
            is_active=not settings.require_confirm_email,
        )
        if invite:
            invite.times_used += 1
            invite.invitees.add(user)
            invite.save()

        if settings.require_confirm_email:
            emailing.email_confirmation_email(user)
            return redirect("confirm-email")

        login(request, user)
        return redirect("get-started-profile")


class ConfirmEmailCode(View):
    """confirm email address"""

    def get(self, request, code):  # pylint: disable=unused-argument
        """you got the code! good work"""
        settings = models.SiteSettings.get()
        if request.user.is_authenticated or not settings.require_confirm_email:
            return redirect("/")

        # look up the user associated with this code
        try:
            user = models.User.objects.get(confirmation_code=code)
        except models.User.DoesNotExist:
            return TemplateResponse(
                request, "confirm_email/confirm_email.html", {"valid": False}
            )
        # update the user
        user.is_active = True
        user.deactivation_reason = None
        user.save(broadcast=False, update_fields=["is_active", "deactivation_reason"])
        # direct the user to log in
        return redirect("login", confirmed="confirmed")


class ConfirmEmail(View):
    """enter code to confirm email address"""

    def get(self, request):  # pylint: disable=unused-argument
        """you need a code! keep looking"""
        settings = models.SiteSettings.get()
        if request.user.is_authenticated or not settings.require_confirm_email:
            return redirect("/")

        return TemplateResponse(
            request, "confirm_email/confirm_email.html", {"valid": True}
        )

    def post(self, request):
        """same as clicking the link"""
        code = request.POST.get("code")
        return ConfirmEmailCode().get(request, code)


@require_POST
def resend_link(request):
    """resend confirmation link"""
    email = request.POST.get("email")
    user = get_object_or_404(models.User, email=email)
    emailing.email_confirmation_email(user)
    return TemplateResponse(
        request, "confirm_email/confirm_email.html", {"valid": True}
    )
