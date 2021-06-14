""" Helping new users figure out the lay of the land """
import re

from django.contrib.auth.decorators import login_required
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models.functions import Greatest
from django.db.models import Count, Q
from django.http import HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms, models
from bookwyrm.connectors import connector_manager
from .helpers import get_suggested_users
from .edit_user import save_user_form


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class GetStartedProfile(View):
    """tell us about yourself"""

    next_view = "get-started-books"

    def get(self, request):
        """basic profile info"""
        data = {
            "form": forms.LimitedEditUserForm(instance=request.user),
            "next": self.next_view,
        }
        return TemplateResponse(request, "get_started/profile.html", data)

    def post(self, request):
        """update your profile"""
        form = forms.LimitedEditUserForm(
            request.POST, request.FILES, instance=request.user
        )
        if not form.is_valid():
            data = {"form": form, "next": "get-started-books"}
            return TemplateResponse(request, "get_started/profile.html", data)
        save_user_form(form)
        return redirect(self.next_view)


@method_decorator(login_required, name="dispatch")
class GetStartedBooks(View):
    """name a book, any book, we gotta start somewhere"""

    next_view = "get-started-users"

    def get(self, request):
        """info about a book"""
        query = request.GET.get("query")
        book_results = popular_books = []
        if query:
            book_results = connector_manager.local_search(query, raw=True)[:5]
        if len(book_results) < 5:
            popular_books = (
                models.Edition.objects.exclude(
                    # exclude already shelved
                    Q(
                        parent_work__in=[
                            b.book.parent_work
                            for b in request.user.shelfbook_set.distinct().all()
                        ]
                    )
                    | Q(  # and exclude if it's already in search results
                        parent_work__in=[b.parent_work for b in book_results]
                    )
                )
                .annotate(Count("shelfbook"))
                .order_by("-shelfbook__count")[: 5 - len(book_results)]
            )

        data = {
            "book_results": book_results,
            "popular_books": popular_books,
            "next": self.next_view,
        }
        return TemplateResponse(request, "get_started/books.html", data)

    def post(self, request):
        """shelve some books"""
        shelve_actions = [
            (k, v)
            for k, v in request.POST.items()
            if re.match(r"\d+", k) and re.match(r"\d+", v)
        ]
        for (book_id, shelf_id) in shelve_actions:
            book = get_object_or_404(models.Edition, id=book_id)
            shelf = get_object_or_404(models.Shelf, id=shelf_id)
            if shelf.user != request.user:
                # hmmmmm
                return HttpResponseNotFound()
            models.ShelfBook.objects.create(book=book, shelf=shelf, user=request.user)
        return redirect(self.next_view)


@method_decorator(login_required, name="dispatch")
class GetStartedUsers(View):
    """find friends"""

    def get(self, request):
        """basic profile info"""
        query = request.GET.get("query")
        user_results = (
            models.User.viewer_aware_objects(request.user)
            .annotate(
                similarity=Greatest(
                    TrigramSimilarity("username", query),
                    TrigramSimilarity("localname", query),
                )
            )
            .filter(
                similarity__gt=0.5,
            )
            .order_by("-similarity")[:5]
        )

        if user_results.count() < 5:
            user_results = list(user_results) + list(get_suggested_users(request.user))

        data = {
            "suggested_users": user_results,
        }
        return TemplateResponse(request, "get_started/users.html", data)
