""" book list views"""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms, models
from bookwyrm.lists_stream import ListsStream
from bookwyrm.models.fields import ForeignKey
from bookwyrm.views.helpers import get_user_from_username


# pylint: disable=no-self-use
class Genres(View):
    """book list page"""

    def get(self, request):
        """display a book list"""
        genres = models.Genre.objects.all()
        paginated = Paginator(genres, 12)
        data = {
            "genres": paginated.get_page(request.GET.get("page")),
            "list_form": forms.ListForm(),
            "path": "/genres",
        }
        return TemplateResponse(request, "genre/genre.html", data)

    @method_decorator(login_required, name="dispatch")
    # pylint: disable=unused-argument
    def post(self, request):
        """create a book_list"""
        form = forms.ListForm(request.POST)
        if not form.is_valid():
            return redirect("lists")
        book_list = form.save(request, commit=False)

        # list should not have a group if it is not group curated
        if not book_list.curation == "group":
            book_list.group = None
        book_list.save()

        return redirect(book_list.local_path)
    
    @method_decorator(login_required, name="dispatch")
    class FollowGenre(View):
        """follow a genre"""

        def post(self, request, pk):
            """follow a genre"""
            genre = models.Genre.objects.get(id=pk)
            user = models.User.objects.get(id=request.user.id)
            user.followed_genres.add(genre)
            return redirect("genres")


    @method_decorator(login_required, name="dispatch")
    class UnFollowGenre(View):
        """unfollow a genre"""

        def post(self, request, pk):
            """unlike a status"""
            genre = models.Genre.objects.get(id=pk)
            user = models.User.objects.get(id=request.user.id)
            user.followed_genres.remove(genre)
            return redirect("followed-genres")


@method_decorator(login_required, name="dispatch")
class FollowedGenres(View):
    """saved book list page"""

    def get(self, request):
        """display book lists"""
        genres = request.user.followed_genres.all()
        paginated = Paginator(genres, 12)
        data = {
            "genres": paginated.get_page(request.GET.get("page")),
            "list_form": forms.ListForm(),
            "path": "/genres",
        }
        return TemplateResponse(request, "genre/genre.html", data)


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
