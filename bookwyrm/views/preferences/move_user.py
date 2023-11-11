""" move your account somewhere else """

from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import forms, models
from bookwyrm.views.helpers import handle_remote_webfinger


# pylint: disable=no-self-use
@method_decorator(login_required, name="dispatch")
class MoveUser(View):
    """move user view"""

    def get(self, request):
        """move page for a user"""
        data = {
            "form": forms.MoveUserForm(),
            "user": request.user,
        }
        return TemplateResponse(request, "preferences/move_user.html", data)

    def post(self, request):
        """Packing your stuff and moving house"""
        form = forms.MoveUserForm(request.POST, instance=request.user)
        user = models.User.objects.get(id=request.user.id)

        if form.is_valid() and user.check_password(form.cleaned_data["password"]):
            username = form.cleaned_data["target"]
            target = handle_remote_webfinger(username)

            try:
                models.MoveUser.objects.create(
                    user=request.user, object=request.user.remote_id, target=target
                )

                return redirect("user-feed", username=request.user.username)

            except PermissionDenied:
                form.errors["target"] = [
                    "Set this user as an alias on the user you are moving to first"
                ]
                data = {"form": form, "user": request.user}
                return TemplateResponse(request, "preferences/move_user.html", data)

        form.errors["password"] = ["Invalid password"]
        data = {"form": form, "user": request.user}
        return TemplateResponse(request, "preferences/move_user.html", data)


# pylint: disable=no-self-use
@method_decorator(login_required, name="dispatch")
class AliasUser(View):
    """alias user view"""

    def get(self, request):
        """move page for a user"""
        data = {
            "form": forms.AliasUserForm(),
            "user": request.user,
        }
        return TemplateResponse(request, "preferences/alias_user.html", data)

    def post(self, request):
        """Creating a nom de plume"""
        form = forms.AliasUserForm(request.POST, instance=request.user)
        user = models.User.objects.get(id=request.user.id)

        if form.is_valid() and user.check_password(form.cleaned_data["password"]):
            username = form.cleaned_data["username"]
            remote_user = handle_remote_webfinger(username)

            if remote_user is None:
                form.errors["username"] = ["Username does not exist"]
                data = {"form": form, "user": request.user}
                return TemplateResponse(request, "preferences/alias_user.html", data)

            user.also_known_as.add(remote_user.id)

            return redirect("prefs-alias")

        form.errors["password"] = ["Invalid password"]
        data = {"form": form, "user": request.user}
        return TemplateResponse(request, "preferences/alias_user.html", data)


@login_required
@require_POST
def remove_alias(request):
    """remove an alias from the user profile"""

    request.user.also_known_as.remove(request.POST["alias"])
    return redirect("prefs-alias")


@require_POST
@login_required
def unmove(request):
    """undo a user move"""
    target = get_object_or_404(models.User, remote_id=request.POST["remote_id"])
    move = get_object_or_404(models.MoveUser, target=target, user=request.user)
    move.delete()

    request.user.moved_to = None
    request.user.save(update_fields=["moved_to"], broadcast=True)
    return redirect("prefs-alias")
