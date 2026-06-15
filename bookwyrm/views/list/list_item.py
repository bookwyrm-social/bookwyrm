"""book list views"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms, models
from bookwyrm.views.helpers import convert_to_markdown, redirect_to_referer
from bookwyrm.views.status import to_markdown


@method_decorator(login_required, name="dispatch")
class ListItem(View):
    """book list page"""

    def post(self, request, list_id, list_item):
        """Edit a list item's notes"""
        return edit_list_item(
            request, list_id, list_item, models.ListItem, forms.ListItemForm
        )


@method_decorator(login_required, name="dispatch")
class SuggestionListItem(View):
    """book suggestion list page"""

    def post(self, request, list_id, list_item):
        """Edit a suggestion list item's notes"""
        return edit_list_item(
            request,
            list_id,
            list_item,
            models.SuggestionListItem,
            forms.SuggestionListItemForm,
        )


def edit_list_item(request, list_id, list_item, item_model, form):
    """edit a list or suggestion list item"""
    list_item = get_object_or_404(item_model, id=list_item, book_list=list_id)
    list_item.raise_not_editable(request.user)

    form = form(request.POST, instance=list_item)
    if form.is_valid():
        item = form.save(request, commit=False)
        item.raw_notes = item.notes
        item.notes = convert_to_markdown(item.notes)
        item.save()
    else:
        raise Exception(form.errors)

    return redirect_to_referer(request)