""" book list views"""
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms, models
from bookwyrm.views.list.list import increment_order_in_reverse
from bookwyrm.views.list.list import normalize_book_list_ordering


# pylint: disable=no-self-use
@method_decorator(login_required, name="dispatch")
class Curate(View):
    """approve or discard list suggestions"""

    def get(self, request, list_id):
        """display a pending list"""
        book_list = get_object_or_404(models.List, id=list_id)
        book_list.raise_not_editable(request.user)

        data = {
            "list": book_list,
            "pending": book_list.listitem_set.filter(approved=False),
            "list_form": forms.ListForm(instance=book_list),
        }
        return TemplateResponse(request, "lists/curate.html", data)

    def post(self, request, list_id):
        """edit a book_list"""
        book_list = get_object_or_404(models.List, id=list_id)

        suggestion = get_object_or_404(models.ListItem, id=request.POST.get("item"))
        approved = request.POST.get("approved") == "true"
        if approved:
            # update the book and set it to be the last in the order of approved books,
            # before any pending books
            suggestion.approved = True
            order_max = (
                book_list.listitem_set.filter(approved=True).aggregate(Max("order"))[
                    "order__max"
                ]
                or 0
            ) + 1
            suggestion.order = order_max
            increment_order_in_reverse(book_list.id, order_max)
            suggestion.save()
        else:
            deleted_order = suggestion.order
            suggestion.delete(broadcast=False)
            normalize_book_list_ordering(book_list.id, start=deleted_order)
        return redirect("list-curate", book_list.id)
