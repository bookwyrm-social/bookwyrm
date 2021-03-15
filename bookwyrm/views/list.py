""" book list views"""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import HttpResponseNotFound, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import forms, models
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.connectors import connector_manager
from .helpers import is_api_request, object_visible_to_user, privacy_filter
from .helpers import get_user_from_username

# pylint: disable=no-self-use
class Lists(View):
    """ book list page """

    def get(self, request):
        """ display a book list """
        try:
            page = int(request.GET.get("page", 1))
        except ValueError:
            page = 1

        user = request.user if request.user.is_authenticated else None
        # hide lists with no approved books
        lists = (
            models.List.objects.filter(
                ~Q(user=user),
            )
            .annotate(item_count=Count("listitem", filter=Q(listitem__approved=True)))
            .filter(item_count__gt=0)
            .distinct()
            .all()
        )
        lists = privacy_filter(
            request.user, lists, privacy_levels=["public", "followers"]
        )

        paginated = Paginator(lists, 12)
        data = {
            "lists": paginated.page(page),
            "list_form": forms.ListForm(),
            "path": "/list",
        }
        return TemplateResponse(request, "lists/lists.html", data)

    @method_decorator(login_required, name="dispatch")
    # pylint: disable=unused-argument
    def post(self, request):
        """ create a book_list """
        form = forms.ListForm(request.POST)
        if not form.is_valid():
            return redirect("lists")
        book_list = form.save()

        return redirect(book_list.local_path)


class UserLists(View):
    """ a user's book list page """

    def get(self, request, username):
        """ display a book list """
        try:
            page = int(request.GET.get("page", 1))
        except ValueError:
            page = 1
        user = get_user_from_username(request.user, username)
        lists = models.List.objects.filter(user=user).all()
        lists = privacy_filter(request.user, lists)
        paginated = Paginator(lists, 12)

        data = {
            "user": user,
            "is_self": request.user.id == user.id,
            "lists": paginated.page(page),
            "list_form": forms.ListForm(),
            "path": user.local_path + "/lists",
        }
        return TemplateResponse(request, "user/lists.html", data)


class List(View):
    """ book list page """

    def get(self, request, list_id):
        """ display a book list """
        book_list = get_object_or_404(models.List, id=list_id)
        if not object_visible_to_user(request.user, book_list):
            return HttpResponseNotFound()

        if is_api_request(request):
            return ActivitypubResponse(book_list.to_activity(**request.GET))

        query = request.GET.get("q")
        suggestions = None
        if query and request.user.is_authenticated:
            # search for books
            suggestions = connector_manager.local_search(query, raw=True)
        elif request.user.is_authenticated:
            # just suggest whatever books are nearby
            suggestions = request.user.shelfbook_set.filter(
                ~Q(book__in=book_list.books.all())
            )
            suggestions = [s.book for s in suggestions[:5]]
            if len(suggestions) < 5:
                suggestions += [
                    s.default_edition
                    for s in models.Work.objects.filter(
                        ~Q(editions__in=book_list.books.all()),
                    ).order_by("-updated_date")
                ][: 5 - len(suggestions)]

        data = {
            "list": book_list,
            "items": book_list.listitem_set.filter(approved=True),
            "pending_count": book_list.listitem_set.filter(approved=False).count(),
            "suggested_books": suggestions,
            "list_form": forms.ListForm(instance=book_list),
            "query": query or "",
        }
        return TemplateResponse(request, "lists/list.html", data)

    @method_decorator(login_required, name="dispatch")
    # pylint: disable=unused-argument
    def post(self, request, list_id):
        """ edit a list """
        book_list = get_object_or_404(models.List, id=list_id)
        form = forms.ListForm(request.POST, instance=book_list)
        if not form.is_valid():
            return redirect("list", book_list.id)
        book_list = form.save()
        return redirect(book_list.local_path)


class Curate(View):
    """ approve or discard list suggestsions """

    @method_decorator(login_required, name="dispatch")
    def get(self, request, list_id):
        """ display a pending list """
        book_list = get_object_or_404(models.List, id=list_id)
        if not book_list.user == request.user:
            # only the creater can curate the list
            return HttpResponseNotFound()

        data = {
            "list": book_list,
            "pending": book_list.listitem_set.filter(approved=False),
            "list_form": forms.ListForm(instance=book_list),
        }
        return TemplateResponse(request, "lists/curate.html", data)

    @method_decorator(login_required, name="dispatch")
    # pylint: disable=unused-argument
    def post(self, request, list_id):
        """ edit a book_list """
        book_list = get_object_or_404(models.List, id=list_id)
        suggestion = get_object_or_404(models.ListItem, id=request.POST.get("item"))
        approved = request.POST.get("approved") == "true"
        if approved:
            suggestion.approved = True
            suggestion.save()
        else:
            suggestion.delete()
        return redirect("list-curate", book_list.id)


@require_POST
def add_book(request):
    """ put a book on a list """
    book_list = get_object_or_404(models.List, id=request.POST.get("list"))
    if not object_visible_to_user(request.user, book_list):
        return HttpResponseNotFound()

    book = get_object_or_404(models.Edition, id=request.POST.get("book"))
    # do you have permission to add to the list?
    try:
        if request.user == book_list.user or book_list.curation == "open":
            # go ahead and add it
            models.ListItem.objects.create(
                book=book,
                book_list=book_list,
                user=request.user,
            )
        elif book_list.curation == "curated":
            # make a pending entry
            models.ListItem.objects.create(
                approved=False,
                book=book,
                book_list=book_list,
                user=request.user,
            )
        else:
            # you can't add to this list, what were you THINKING
            return HttpResponseBadRequest()
    except IntegrityError:
        # if the book is already on the list, don't flip out
        pass

    return redirect("list", book_list.id)


@require_POST
def remove_book(request, list_id):
    """ put a book on a list """
    book_list = get_object_or_404(models.List, id=list_id)
    item = get_object_or_404(models.ListItem, id=request.POST.get("item"))

    if not book_list.user == request.user and not item.user == request.user:
        return HttpResponseNotFound()

    item.delete()
    return redirect("list", list_id)
