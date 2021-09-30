""" class views for password management """
from django.contrib.auth import login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.translation import gettext_lazy as _
from django.views import View

from bookwyrm import models
from bookwyrm.emailing import password_reset_email


# pylint: disable= no-self-use
class PasswordResetRequest(View):
    """forgot password flow"""

    def get(self, request):
        """password reset page"""
        return TemplateResponse(
            request,
            "password_reset_request.html",
        )

    def post(self, request):
        """create a password reset token"""
        email = request.POST.get("email")
        try:
            user = models.User.viewer_aware_objects(request.user).get(
                email=email, email__isnull=False
            )
        except models.User.DoesNotExist:
            data = {"error": _("No user with that email address was found.")}
            return TemplateResponse(request, "password_reset_request.html", data)

        # remove any existing password reset cods for this user
        models.PasswordReset.objects.filter(user=user).all().delete()

        # create a new reset code
        code = models.PasswordReset.objects.create(user=user)
        password_reset_email(code)
        data = {"message": _(f"A password reset link sent to {email}")}
        return TemplateResponse(request, "password_reset_request.html", data)


class PasswordReset(View):
    """set new password"""

    def get(self, request, code):
        """endpoint for sending invites"""
        if request.user.is_authenticated:
            return redirect("/")
        try:
            reset_code = models.PasswordReset.objects.get(code=code)
            if not reset_code.valid():
                raise PermissionDenied()
        except models.PasswordReset.DoesNotExist:
            raise PermissionDenied()

        return TemplateResponse(request, "password_reset.html", {"code": code})

    def post(self, request, code):
        """allow a user to change their password through an emailed token"""
        try:
            reset_code = models.PasswordReset.objects.get(code=code)
        except models.PasswordReset.DoesNotExist:
            data = {"errors": ["Invalid password reset link"]}
            return TemplateResponse(request, "password_reset.html", data)

        user = reset_code.user

        new_password = request.POST.get("password")
        confirm_password = request.POST.get("confirm-password")

        if new_password != confirm_password:
            data = {"errors": ["Passwords do not match"]}
            return TemplateResponse(request, "password_reset.html", data)

        user.set_password(new_password)
        user.save(broadcast=False, update_fields=["password"])
        login(request, user)
        reset_code.delete()
        return redirect("/")
