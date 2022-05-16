""" class views for login/register views """
from django.contrib.auth import login
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
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
        # no registration allowed when the site is being installed
        if settings.install_mode:
            raise PermissionDenied()

        if not settings.allow_registration:
            invite_code = request.POST.get("invite_code")

            if not invite_code:
                raise PermissionDenied()

            invite = get_object_or_404(models.SiteInvite, code=invite_code)
            if not invite.valid():
                raise PermissionDenied()
        else:
            invite = None

        form = forms.RegisterForm(request.POST)
        if not form.is_valid():
            data = {
                "login_form": forms.LoginForm(),
                "register_form": form,
                "invite": invite,
                "valid": invite.valid() if invite else True,
            }
            if invite:
                return TemplateResponse(request, "landing/invite.html", data)
            return TemplateResponse(request, "landing/login.html", data)

        localname = form.data["localname"].strip()
        email = form.data["email"]
        password = form.data["password"]

        # make sure the email isn't blocked as spam
        email_domain = email.split("@")[-1]
        if models.EmailBlocklist.objects.filter(domain=email_domain).exists():
            # treat this like a successful registration, but don't do anything
            return redirect("confirm-email")

        username = f"{localname}@{DOMAIN}"
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
        if request.user.is_authenticated:
            return redirect("/")

        if not settings.require_confirm_email:
            return redirect("login")

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


class ResendConfirmEmail(View):
    """you probably didn't get the email because celery is slow but you can try this"""

    def get(self, request, error=False):
        """resend link landing page"""
        return TemplateResponse(request, "confirm_email/resend.html", {"error": error})

    def post(self, request):
        """resend confirmation link"""
        email = request.POST.get("email")
        try:
            user = models.User.objects.get(email=email)
        except models.User.DoesNotExist:
            return self.get(request, error=True)

        emailing.email_confirmation_email(user)
        return TemplateResponse(
            request, "confirm_email/confirm_email.html", {"valid": True}
        )
