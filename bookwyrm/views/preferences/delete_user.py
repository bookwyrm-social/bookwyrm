""" edit your own account """
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
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
        """les get fancy with images"""
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
