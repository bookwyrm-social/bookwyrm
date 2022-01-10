""" Manage link domains"""
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
class LinkDomain(View):
    """Moderate links"""

    def get(self, request, status):
        """view pending domains"""
        data = {
            "domains": models.LinkDomain.objects.filter(
                status=status
            ).prefetch_related("links"),
            "form": forms.EmailBlocklistForm(),
            "status": status,
        }
        return TemplateResponse(
            request, "settings/link_domains/link_domains.html", data
        )

    def post(self, request, status, domain_id):
        """Set display name"""
        domain = get_object_or_404(models.LinkDomain, id=domain_id)
        form = forms.LinkDomainForm(request.POST, instance=domain)
        form.save()
        return redirect('settings-link-domain', status=status)
