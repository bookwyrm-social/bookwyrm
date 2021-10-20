""" Manage IP blocklist """
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
class IPBlocklist(View):
    """Block registration by ip address"""

    def get(self, request):
        """view and compose blocks"""
        data = {
            "addresses": models.IPBlocklist.objects.all(),
            "form": forms.IPBlocklistForm(),
        }
        return TemplateResponse(
            request, "settings/ip_blocklist/ip_blocklist.html", data
        )

    def post(self, request, block_id=None):
        """create a new ip address block"""
        if block_id:
            return self.delete(request, block_id)

        form = forms.IPBlocklistForm(request.POST)
        data = {
            "addresses": models.IPBlocklist.objects.all(),
            "form": form,
        }
        if not form.is_valid():
            return TemplateResponse(
                request, "settings/ip_blocklist/ip_blocklist.html", data
            )
        form.save()

        data["form"] = forms.IPBlocklistForm()
        return TemplateResponse(
            request, "settings/ip_blocklist/ip_blocklist.html", data
        )

    # pylint: disable=unused-argument
    def delete(self, request, domain_id):
        """remove a domain block"""
        domain = get_object_or_404(models.IPBlocklist, id=domain_id)
        domain.delete()
        return redirect("settings-ip-blocks")
