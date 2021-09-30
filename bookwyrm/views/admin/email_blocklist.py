""" Manage email blocklist"""
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect
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
    """Block registration by email address"""

    def get(self, request):
        """view and compose blocks"""
        data = {
            "domains": models.EmailBlocklist.objects.order_by("-created_date").all(),
            "form": forms.EmailBlocklistForm(),
        }
        return TemplateResponse(
            request, "settings/email_blocklist/email_blocklist.html", data
        )

    def post(self, request, domain_id=None):
        """create a new domain block"""
        if domain_id:
            return self.delete(request, domain_id)

        form = forms.EmailBlocklistForm(request.POST)
        data = {
            "domains": models.EmailBlocklist.objects.order_by("-created_date").all(),
            "form": form,
        }
        if not form.is_valid():
            return TemplateResponse(
                request, "settings/email_blocklist/email_blocklist.html", data
            )
        form.save()

        data["form"] = forms.EmailBlocklistForm()
        return TemplateResponse(
            request, "settings/email_blocklist/email_blocklist.html", data
        )

    # pylint: disable=unused-argument
    def delete(self, request, domain_id):
        """remove a domain block"""
        domain = get_object_or_404(models.EmailBlocklist, id=domain_id)
        domain.delete()
        return redirect("settings-email-blocks")
