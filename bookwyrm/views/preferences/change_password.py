""" class views for password management """
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.debug import sensitive_variables, sensitive_post_parameters

from bookwyrm import models


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class ChangePassword(View):
    """change password as logged in user"""

    def get(self, request):
        """change password page"""
        data = {"user": request.user}
        return TemplateResponse(request, "preferences/change_password.html", data)

    @sensitive_variables("new_password")
    @sensitive_variables("confirm_password")
    @method_decorator(sensitive_post_parameters("current_password"))
    @method_decorator(sensitive_post_parameters("password"))
    @method_decorator(sensitive_post_parameters("confirm__password"))
    def post(self, request):
        """allow a user to change their password"""
        data = {"user": request.user}

        # check current password
        user = models.User.objects.get(id=request.user.id)
        if not user.check_password(request.POST.get("current_password")):
            data["errors"] = {"current_password": [_("Incorrect password")]}
            return TemplateResponse(request, "preferences/change_password.html", data)

        new_password = request.POST.get("password")
        confirm_password = request.POST.get("confirm-password")

        if new_password != confirm_password:
            data["errors"] = {"confirm_password": [_("Password does not match")]}
            return TemplateResponse(request, "preferences/change_password.html", data)

        request.user.set_password(new_password)
        request.user.save(broadcast=False, update_fields=["password"])
        login(request, request.user)
        data["success"] = True
        return TemplateResponse(request, "preferences/change_password.html", data)
