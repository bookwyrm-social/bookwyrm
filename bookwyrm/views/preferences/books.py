from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator

from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import activitystreams, models


@method_decorator(login_required, name="dispatch")
class BlockedBooks(View):
    """show book blocks page"""

    def get(self, request):
        """list of blocked books"""
        return TemplateResponse(request, "preferences/books.html")

    def post(self, request, book_id):
        """block a book"""

        edition = get_object_or_404(models.Edition, id=book_id)
        # first, add work to blocked_books
        request.user.blocked_books.add(edition.parent_work)
        # now remove from streams
        # we only have to do this once because it filters on the parent work
        activitystreams.remove_blocked_book_statuses_task.delay(
            request.user.id, edition.id
        )

        return redirect("prefs-block-books")


@login_required
@require_POST
def unblock_book(request, book_id):
    """unblock a book"""

    edition = get_object_or_404(models.Edition, id=book_id)
    # first, remove work from blocked_books
    request.user.blocked_books.remove(edition.parent_work)
    # now add to streams
    activitystreams.add_blocked_book_statuses_task.delay(request.user.id, edition.id)

    return redirect("prefs-block-books")
