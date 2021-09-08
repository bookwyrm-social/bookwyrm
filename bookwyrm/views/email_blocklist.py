""" moderation via flagged posts and users """
from django.contrib.auth.decorators import login_required, permission_required
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms, models

# pylint: disable=no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.moderate_user", raise_exception=True),
    name="dispatch",
)
class EmailBlocklist(View):
    """Block users by email address"""

    def get(self, request):
        """view and compose blocks"""
        data = {
            "domains": models.EmailBlocklist.objects.order_by("-created_date").all(),
            "form": forms.EmailBlocklistForm(),
        }
        return TemplateResponse(request, "settings/email_blocklist.html", data)
