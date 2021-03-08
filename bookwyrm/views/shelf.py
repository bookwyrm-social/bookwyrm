""" shelf views"""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import forms, models
from bookwyrm.activitypub import ActivitypubResponse
from .helpers import is_api_request, get_edition, get_user_from_username
from .helpers import handle_reading_status


# pylint: disable= no-self-use
class Shelf(View):
    """ shelf page """

    def get(self, request, username, shelf_identifier):
        """ display a shelf """
        try:
            user = get_user_from_username(request.user, username)
        except models.User.DoesNotExist:
            return HttpResponseNotFound()

        if shelf_identifier:
            shelf = user.shelf_set.get(identifier=shelf_identifier)
        else:
            shelf = user.shelf_set.first()

        is_self = request.user == user

        shelves = user.shelf_set
        if not is_self:
            follower = user.followers.filter(id=request.user.id).exists()
            # make sure the user has permission to view the shelf
            if shelf.privacy == "direct" or (
                shelf.privacy == "followers" and not follower
            ):
                return HttpResponseNotFound()

            # only show other shelves that should be visible
            if follower:
                shelves = shelves.filter(privacy__in=["public", "followers"])
            else:
                shelves = shelves.filter(privacy="public")

        if is_api_request(request):
            return ActivitypubResponse(shelf.to_activity(**request.GET))

        books = (
            models.ShelfBook.objects.filter(user=user, shelf=shelf)
            .order_by("-updated_date")
            .all()
        )

        data = {
            "user": user,
            "is_self": is_self,
            "shelves": shelves.all(),
            "shelf": shelf,
            "books": [b.book for b in books],
        }

        return TemplateResponse(request, "user/shelf.html", data)

    @method_decorator(login_required, name="dispatch")
    # pylint: disable=unused-argument
    def post(self, request, username, shelf_identifier):
        """ edit a shelf """
        try:
            shelf = request.user.shelf_set.get(identifier=shelf_identifier)
        except models.Shelf.DoesNotExist:
            return HttpResponseNotFound()

        if request.user != shelf.user:
            return HttpResponseBadRequest()
        if not shelf.editable and request.POST.get("name") != shelf.name:
            return HttpResponseBadRequest()

        form = forms.ShelfForm(request.POST, instance=shelf)
        if not form.is_valid():
            return redirect(shelf.local_path)
        shelf = form.save()
        return redirect(shelf.local_path)


def user_shelves_page(request, username):
    """ default shelf """
    return Shelf.as_view()(request, username, None)


@login_required
@require_POST
def create_shelf(request):
    """ user generated shelves """
    form = forms.ShelfForm(request.POST)
    if not form.is_valid():
        return redirect(request.headers.get("Referer", "/"))

    shelf = form.save()
    return redirect("/user/%s/shelf/%s" % (request.user.localname, shelf.identifier))


@login_required
@require_POST
def delete_shelf(request, shelf_id):
    """ user generated shelves """
    shelf = get_object_or_404(models.Shelf, id=shelf_id)
    if request.user != shelf.user or not shelf.editable:
        return HttpResponseBadRequest()

    shelf.delete()
    return redirect("/user/%s/shelves" % request.user.localname)


@login_required
@require_POST
def shelve(request):
    """ put a  on a user's shelf """
    book = get_edition(request.POST.get("book"))

    desired_shelf = models.Shelf.objects.filter(
        identifier=request.POST.get("shelf"), user=request.user
    ).first()
    if not desired_shelf:
        return HttpResponseNotFound()

    if request.POST.get("reshelve", True):
        try:
            current_shelf = models.Shelf.objects.get(user=request.user, edition=book)
            handle_unshelve(request.user, book, current_shelf)
        except models.Shelf.DoesNotExist:
            # this just means it isn't currently on the user's shelves
            pass
    models.ShelfBook.objects.create(book=book, shelf=desired_shelf, user=request.user)

    # post about "want to read" shelves
    if desired_shelf.identifier == "to-read" and request.POST.get("post-status"):
        privacy = request.POST.get("privacy") or desired_shelf.privacy
        handle_reading_status(request.user, desired_shelf, book, privacy=privacy)

    return redirect("/")


@login_required
@require_POST
def unshelve(request):
    """ put a  on a user's shelf """
    book = models.Edition.objects.get(id=request.POST["book"])
    current_shelf = models.Shelf.objects.get(id=request.POST["shelf"])

    handle_unshelve(request.user, book, current_shelf)
    return redirect(request.headers.get("Referer", "/"))


# pylint: disable=unused-argument
def handle_unshelve(user, book, shelf):
    """ unshelve a book """
    row = models.ShelfBook.objects.get(book=book, shelf=shelf)
    row.delete()
