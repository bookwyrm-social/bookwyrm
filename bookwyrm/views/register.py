""" class views for login/register views """
from django.contrib.auth import login
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from django.views.decorators.debug import sensitive_variables, sensitive_post_parameters

from bookwyrm import emailing, forms, models
from bookwyrm.settings import DOMAIN


# pylint: disable=no-self-use
class Register(View):
    """register a user"""

    def get(self, request):  # pylint: disable=unused-argument
        """whether or not you're logged in, just go to the home view"""
        return redirect("/")

    @sensitive_variables("password")
    @method_decorator(sensitive_post_parameters("password"))
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

        # make sure the email isn't blocked as spam
        email_domain = email.split("@")[-1]
        if models.EmailBlocklist.objects.filter(domain=email_domain).exists():
            # treat this like a successful registration, but don't do anything
            return redirect("confirm-email")

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
