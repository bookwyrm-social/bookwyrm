""" book list views"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms, models
from bookwyrm.views.status import to_markdown


# pylint: disable=no-self-use
@method_decorator(login_required, name="dispatch")
class ListItem(View):
    """book list page"""

    def post(self, request, list_id, list_item):
        """Edit a list item's notes"""
        list_item = get_object_or_404(models.ListItem, id=list_item, book_list=list_id)
        form = forms.ListItemForm(request.POST, instance=list_item)
        if form.is_valid():
            item = form.save(request, commit=False)
            item.notes = to_markdown(item.notes)
            item.save()
        else:
            raise Exception(form.errors)
        return redirect("list", list_item.book_list.id)
