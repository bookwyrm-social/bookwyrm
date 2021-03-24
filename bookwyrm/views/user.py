""" non-interactive pages """
from io import BytesIO
from uuid import uuid4
from PIL import Image

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.http import HttpResponseNotFound
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms, models
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.settings import PAGE_LENGTH
from .helpers import get_user_from_username, is_api_request
from .helpers import is_blocked, privacy_filter, object_visible_to_user


# pylint: disable= no-self-use
class User(View):
    """ user profile page """

    def get(self, request, username):
        """ profile page for a user """
        try:
            user = get_user_from_username(request.user, username)
        except models.User.DoesNotExist:
            return HttpResponseNotFound()

        # make sure we're not blocked
        if is_blocked(request.user, user):
            return HttpResponseNotFound()

        if is_api_request(request):
            # we have a json request
            return ActivitypubResponse(user.to_activity())
        # otherwise we're at a UI view

        try:
            page = int(request.GET.get("page", 1))
        except ValueError:
            page = 1

        shelf_preview = []

        # only show other shelves that should be visible
        shelves = user.shelf_set
        is_self = request.user.id == user.id
        if not is_self:
            follower = user.followers.filter(id=request.user.id).exists()
            if follower:
                shelves = shelves.filter(privacy__in=["public", "followers"])
            else:
                shelves = shelves.filter(privacy="public")

        for user_shelf in shelves.all():
            if not user_shelf.books.count():
                continue
            shelf_preview.append(
                {
                    "name": user_shelf.name,
                    "local_path": user_shelf.local_path,
                    "books": user_shelf.books.all()[:3],
                    "size": user_shelf.books.count(),
                }
            )
            if len(shelf_preview) > 2:
                break

        # user's posts
        activities = privacy_filter(
            request.user,
            user.status_set.select_subclasses(),
        )
        paginated = Paginator(activities, PAGE_LENGTH)
        goal = models.AnnualGoal.objects.filter(
            user=user, year=timezone.now().year
        ).first()
        if not object_visible_to_user(request.user, goal):
            goal = None
        data = {
            "user": user,
            "is_self": is_self,
            "shelves": shelf_preview,
            "shelf_count": shelves.count(),
            "activities": paginated.page(page),
            "goal": goal,
        }

        return TemplateResponse(request, "user/user.html", data)


class Followers(View):
    """ list of followers view """

    def get(self, request, username):
        """ list of followers """
        try:
            user = get_user_from_username(request.user, username)
        except models.User.DoesNotExist:
            return HttpResponseNotFound()

        # make sure we're not blocked
        if is_blocked(request.user, user):
            return HttpResponseNotFound()

        if is_api_request(request):
            return ActivitypubResponse(user.to_followers_activity(**request.GET))

        data = {
            "user": user,
            "is_self": request.user.id == user.id,
            "followers": user.followers.all(),
        }
        return TemplateResponse(request, "user/followers.html", data)


class Following(View):
    """ list of following view """

    def get(self, request, username):
        """ list of followers """
        try:
            user = get_user_from_username(request.user, username)
        except models.User.DoesNotExist:
            return HttpResponseNotFound()

        # make sure we're not blocked
        if is_blocked(request.user, user):
            return HttpResponseNotFound()

        if is_api_request(request):
            return ActivitypubResponse(user.to_following_activity(**request.GET))

        data = {
            "user": user,
            "is_self": request.user.id == user.id,
            "following": user.following.all(),
        }
        return TemplateResponse(request, "user/following.html", data)


@method_decorator(login_required, name="dispatch")
class EditUser(View):
    """ edit user view """

    def get(self, request):
        """ edit profile page for a user """
        data = {
            "form": forms.EditUserForm(instance=request.user),
            "user": request.user,
        }
        return TemplateResponse(request, "preferences/edit_user.html", data)

    def post(self, request):
        """ les get fancy with images """
        form = forms.EditUserForm(request.POST, request.FILES, instance=request.user)
        if not form.is_valid():
            data = {"form": form, "user": request.user}
            return TemplateResponse(request, "preferences/edit_user.html", data)

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

        return redirect(user.local_path)


def crop_avatar(image):
    """ reduce the size and make an avatar square """
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
