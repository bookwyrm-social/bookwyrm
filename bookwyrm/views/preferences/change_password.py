""" class views for password management """
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class ChangePassword(View):
    """change password as logged in user"""

    def get(self, request):
        """change password page"""
        data = {"user": request.user}
        return TemplateResponse(request, "preferences/change_password.html", data)

    def post(self, request):
        """allow a user to change their password"""
        new_password = request.POST.get("password")
        confirm_password = request.POST.get("confirm-password")

        if new_password != confirm_password:
            return redirect("prefs-password")

        request.user.set_password(new_password)
        request.user.save(broadcast=False, update_fields=["password"])
        login(request, request.user)
        return redirect("user-feed", request.user.localname)
