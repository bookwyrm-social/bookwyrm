""" class views for password management """
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.debug import sensitive_variables, sensitive_post_parameters

from bookwyrm import forms


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class ChangePassword(View):
    """change password as logged in user"""

    def get(self, request):
        """change password page"""
        data = {"form": forms.ChangePasswordForm()}
        return TemplateResponse(request, "preferences/change_password.html", data)

    @method_decorator(sensitive_variables("new_password"))
    @method_decorator(sensitive_post_parameters("current_password"))
    @method_decorator(sensitive_post_parameters("password"))
    @method_decorator(sensitive_post_parameters("confirm_password"))
    def post(self, request):
        """allow a user to change their password"""
        form = forms.ChangePasswordForm(request.POST, instance=request.user)
        if not form.is_valid():
            data = {"form": form}
            return TemplateResponse(request, "preferences/change_password.html", data)

        new_password = form.cleaned_data["password"]
        request.user.set_password(new_password)
        request.user.save(broadcast=False, update_fields=["password"])

        login(request, request.user)
        data = {"success": True, "form": forms.ChangePasswordForm()}
        return TemplateResponse(request, "preferences/change_password.html", data)
