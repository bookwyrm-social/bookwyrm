""" edit your own account """
import time

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms, models


# pylint: disable=no-self-use
@method_decorator(login_required, name="dispatch")
class DeleteUser(View):
    """delete user view"""

    def get(self, request):
        """delete page for a user"""
        data = {
            "form": forms.DeleteUserForm(),
            "user": request.user,
        }
        return TemplateResponse(request, "preferences/delete_user.html", data)

    def post(self, request):
        """There's no going back from this"""
        form = forms.DeleteUserForm(request.POST, instance=request.user)
        # idk why but I couldn't get check_password to work on request.user
        user = models.User.objects.get(id=request.user.id)
        if form.is_valid() and user.check_password(form.cleaned_data["password"]):
            user.deactivation_reason = "self_deletion"
            user.delete()
            logout(request)
            return redirect("/")

        form.errors["password"] = ["Invalid password"]
        data = {"form": form, "user": request.user}
        return TemplateResponse(request, "preferences/delete_user.html", data)


@method_decorator(login_required, name="dispatch")
class DeactivateUser(View):
    """deactivate user view"""

    def post(self, request):
        """You can reactivate"""
        request.user.deactivate()
        logout(request)
        return redirect("/")


class ReactivateUser(View):
    """now reactivate the user"""

    def get(self, request):
        """so you want to rejoin?"""
        if request.user.is_authenticated:
            return redirect("/")
        data = {"login_form": forms.LoginForm()}
        return TemplateResponse(request, "landing/reactivate.html", data)

    def post(self, request):
        """reactivate that baby"""
        login_form = forms.LoginForm(request.POST)

        username = login_form.infer_username()
        password = login_form.data.get("password")
        user = get_object_or_404(models.User, username=username)

        # we can't use "authenticate" because that requires an active user
        if not user.check_password(password):
            login_form.add_invalid_password_error()
            data = {"login_form": login_form}
            return TemplateResponse(request, "landing/reactivate.html", data)

        # Correct password, do you need 2fa too?
        if user.two_factor_auth:
            request.session["2fa_user"] = user.username
            request.session["2fa_auth_time"] = time.time()
            return redirect("login-with-2fa")

        user.reactivate()
        login(request, user)
        return redirect("/")
