""" edit or delete ones own account"""
from io import BytesIO
from uuid import uuid4
from PIL import Image

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms, models


# pylint: disable=no-self-use
@method_decorator(login_required, name="dispatch")
class EditUser(View):
    """edit user view"""

    def get(self, request):
        """edit profile page for a user"""
        data = {
            "form": forms.EditUserForm(instance=request.user),
            "user": request.user,
        }
        return TemplateResponse(request, "preferences/edit_user.html", data)

    def post(self, request):
        """les get fancy with images"""
        form = forms.EditUserForm(request.POST, request.FILES, instance=request.user)
        if not form.is_valid():
            data = {"form": form, "user": request.user}
            return TemplateResponse(request, "preferences/edit_user.html", data)

        user = save_user_form(form)

        return redirect(user.local_path)


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
        form.is_valid()
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


def save_user_form(form):
    """special handling for the user form"""
    user = form.save(commit=False)

    if "avatar" in form.files:
        # crop and resize avatar upload
        image = Image.open(form.files["avatar"])
        image = crop_avatar(image)

        # set the name to a hash
        extension = form.files["avatar"].name.split(".")[-1]
        filename = "%s.%s" % (uuid4(), extension)
        user.avatar.save(filename, image, save=False)
    user.save()
    return user


def crop_avatar(image):
    """reduce the size and make an avatar square"""
    target_size = 120
    width, height = image.size
    thumbnail_scale = (
        height / (width / target_size)
        if height > width
        else width / (height / target_size)
    )
    image.thumbnail([thumbnail_scale, thumbnail_scale])
    width, height = image.size

    width_diff = width - target_size
    height_diff = height - target_size
    cropped = image.crop(
        (
            int(width_diff / 2),
            int(height_diff / 2),
            int(width - (width_diff / 2)),
            int(height - (height_diff / 2)),
        )
    )
    output = BytesIO()
    cropped.save(output, format=image.format)
    return ContentFile(output.getvalue())
