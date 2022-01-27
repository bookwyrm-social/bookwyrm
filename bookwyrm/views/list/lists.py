""" book list views"""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms, models
from bookwyrm.lists_stream import ListsStream
from bookwyrm.views.helpers import get_user_from_username


# pylint: disable=no-self-use
class Lists(View):
    """book list page"""

    def get(self, request):
        """display a book list"""
        lists = ListsStream().get_list_stream(request.user)
        paginated = Paginator(lists, 12)
        data = {
            "lists": paginated.get_page(request.GET.get("page")),
            "list_form": forms.ListForm(),
            "path": "/list",
        }
        return TemplateResponse(request, "lists/lists.html", data)

    @method_decorator(login_required, name="dispatch")
    # pylint: disable=unused-argument
    def post(self, request):
        """create a book_list"""
        form = forms.ListForm(request.POST)
        if not form.is_valid():
            return redirect("lists")
        book_list = form.save()
        # list should not have a group if it is not group curated
        if not book_list.curation == "group":
            book_list.group = None
            book_list.save(broadcast=False)

        return redirect(book_list.local_path)


@method_decorator(login_required, name="dispatch")
class SavedLists(View):
    """saved book list page"""

    def get(self, request):
        """display book lists"""
        # hide lists with no approved books
        lists = request.user.saved_lists.order_by("-updated_date")

        paginated = Paginator(lists, 12)
        data = {
            "lists": paginated.get_page(request.GET.get("page")),
            "list_form": forms.ListForm(),
            "path": "/list",
        }
        return TemplateResponse(request, "lists/lists.html", data)


@method_decorator(login_required, name="dispatch")
class UserLists(View):
    """a user's book list page"""

    def get(self, request, username):
        """display a book list"""
        user = get_user_from_username(request.user, username)
        lists = models.List.privacy_filter(request.user).filter(user=user)
        paginated = Paginator(lists, 12)

        data = {
            "user": user,
            "is_self": request.user.id == user.id,
            "lists": paginated.get_page(request.GET.get("page")),
            "list_form": forms.ListForm(),
            "path": user.local_path + "/lists",
        }
        return TemplateResponse(request, "user/lists.html", data)
