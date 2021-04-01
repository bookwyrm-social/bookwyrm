""" Helping new users figure out the lay of the land """
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms, models
from bookwyrm.connectors import connector_manager
from .helpers import get_suggested_users
from .user import save_user_form


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class GetStartedProfile(View):
    """ tell us about yourself """

    def get(self, request):
        """ basic profile info """
        data = {
            "form": forms.LimitedEditUserForm(instance=request.user),
            "next": "get-started-books",
        }
        return TemplateResponse(request, "get_started/profile.html", data)

    def post(self, request):
        """ update your profile """
        form = forms.LimitedEditUserForm(
            request.POST, request.FILES, instance=request.user
        )
        if not form.is_valid():
            data = {"form": form, "next": "get-started-books"}
            return TemplateResponse(request, "get_started/profile.html", data)
        save_user_form(form)
        return redirect('get-started-books')


@method_decorator(login_required, name="dispatch")
class GetStartedBooks(View):
    """ name a book, any book, we gotta start somewhere """

    def get(self, request):
        """ info about a book """
        query = request.GET.get("query")
        book_results = []
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
                    |  # - or if it's already in search results
                    Q(parent_work__in=[b.parent_work for b in book_results])
                )
                .annotate(Count("shelfbook"))
                .order_by("-shelfbook__count")[: 5 - len(book_results)]
            )

        data = {
            "book_results": book_results,
            "popular_books": popular_books,
            "next": "get-started-users",
        }
        return TemplateResponse(request, "get_started/books.html", data)


@method_decorator(login_required, name="dispatch")
class GetStartedUsers(View):
    """ find friends """

    def get(self, request):
        """ basic profile info """
        suggested_users = (
            get_suggested_users(
                request.user,
                ~Q(id=request.user.id),
                ~Q(followers=request.user),
                bookwyrm_user=True,
            )
            .order_by("shared_books", "-mutuals", "-last_active_date")
            .all()[:5]
        )
        data = {
            "suggested_users": suggested_users,
            "next": "get-started-profile",
        }
        return TemplateResponse(request, "get_started/users.html", data)
