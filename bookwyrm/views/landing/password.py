"""class views for password management"""

from django.contrib.auth import login
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.translation import gettext_lazy as _
from django.views import View

from bookwyrm import forms, models
from bookwyrm.emailing import password_reset_email


class PasswordResetRequest(View):
    """forgot password flow"""

    def get(self, request):
        """password reset page"""
        return TemplateResponse(
            request,
            "landing/password_reset_request.html",
        )

    def post(self, request):
        """create a password reset token"""
        email = request.POST.get("email")
        data = {"sent_message": True, "email": email}
        try:
            user = models.User.viewer_aware_objects(request.user).get(
                email=email, email__isnull=False
            )
        except models.User.DoesNotExist:
            # Showing an error message would leak whether or not this email is in use
            return TemplateResponse(
                request, "landing/password_reset_request.html", data
            )

        # remove any existing password reset cods for this user
        models.PasswordReset.objects.filter(user=user).all().delete()

        # create a new reset code
        code = models.PasswordReset.objects.create(user=user)
        password_reset_email(code)
        return TemplateResponse(request, "landing/password_reset_request.html", data)


class PasswordReset(View):
    """set new password"""

    def get(self, request, code):
        """endpoint for password reset"""
        if request.user.is_authenticated:
            return redirect("/")
        try:
            reset_code = models.PasswordReset.objects.get(code=code)
            if not reset_code.valid():
                raise PermissionDenied()
        except models.PasswordReset.DoesNotExist:
            raise PermissionDenied()

        data = {"code": code, "form": forms.PasswordResetForm()}
        return TemplateResponse(request, "landing/password_reset.html", data)

    def post(self, request, code):
        """allow a user to change their password through an emailed token"""
        try:
            reset_code = models.PasswordReset.objects.get(code=code)
        except models.PasswordReset.DoesNotExist:
            data = {"errors": ["Invalid password reset link"]}
            return TemplateResponse(request, "landing/password_reset.html", data)

        user = reset_code.user
        form = forms.PasswordResetForm(request.POST, instance=user)
        if not form.is_valid():
            data = {"code": code, "form": form}
            return TemplateResponse(request, "landing/password_reset.html", data)

        new_password = form.cleaned_data["password"]
        user.set_password(new_password)
        user.save(broadcast=False, update_fields=["password"])
        login(request, user)
        reset_code.delete()
        return redirect("/")


class ForcePasswordReset(View):
    """require user to set new password"""

    def get(self, request):
        """endpoint for forced password resets"""
        if request.user.is_authenticated:
            return redirect("/")

        # only show this view to users that need to reset their passwords
        if not models.User.objects.filter(
            username=request.session.get("force_reset_password_user"),
            force_password_reset=True,
        ).exists():
            return redirect("/")

        data = {"form": forms.ForcePasswordResetForm()}
        return TemplateResponse(request, "landing/force_password_reset.html", data)

    def post(self, request):
        """require a user to change their password"""
        try:
            user = models.User.objects.get(
                username=request.session.get("force_reset_password_user"),
                force_password_reset=True,
            )
        except ObjectDoesNotExist:
            return HttpResponseBadRequest("Invalid user")

        form = forms.ForcePasswordResetForm(request.POST, instance=user)
        if not user.check_password(form.data["current_password"]):
            form.add_error("current_password", _("Incorrect password"))
            return TemplateResponse(
                request, "landing/force_password_reset.html", {"form": form}
            )
        if not form.is_valid():
            return TemplateResponse(
                request, "landing/force_password_reset.html", {"form": form}
            )

        new_password = form.cleaned_data["password"]
        user.set_password(new_password)
        user.force_password_reset = False
        user.save(broadcast=False, update_fields=["password", "force_password_reset"])
        login(request, user)
        return redirect("/")
