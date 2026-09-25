"""Data quality problems"""

from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q
from django.db.models.functions import Length
from django.db.models.query import QuerySet
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import models


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.manage_data", raise_exception=True),
    name="dispatch",
)
class DataProblems(View):
    """deduplication task settings"""

    def get(self, request):
        """view maintenance task settings"""
        # Eventually this view should also include orphaned editions,
        # series with blank names, and authors with no books
        isbn_length = get_invalid_isbns()
        data = {
            "isbn_length": isbn_length,
            "isbn_length_dupes_unblocked": isbn_length.filter(
                merge_target__isnull=False, prevent_automatic_merge=False
            ),
            "isbn_length_dupes_blocked": isbn_length.filter(
                merge_target__isnull=False, prevent_automatic_merge=True
            ),
        }

        return TemplateResponse(request, "settings/manage_data/problems.html", data)


@require_POST
@permission_required("bookwyrm.manage_data", raise_exception=True)
def block_problem_merges(request):
    """prevent automatic merge of books with invalid ISBNs"""
    editions = get_invalid_isbns().filter(merge_target__isnull=False)
    editions.update(
        prevent_automatic_merge=True, prevent_automatic_merge_user=request.user
    )
    return redirect("settings-problems")


def get_invalid_isbns() -> QuerySet[models.Edition]:
    """any edition with an ISBN of the wrong length"""
    return (
        models.Edition.objects.annotate(
            len_10=Length("isbn_10"), len_13=Length("isbn_13")
        )
        .exclude(Q(Q(len_13=13) | Q(len_13=0)) & Q(Q(len_10=10) | Q(len_10=0)))
        .distinct()
    )
