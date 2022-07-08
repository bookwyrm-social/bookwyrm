""" Manage link domains"""
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import forms, models

# pylint: disable=no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.moderate_user", raise_exception=True),
    name="dispatch",
)
class LinkDomain(View):
    """Moderate links"""

    def get(self, request, status="pending"):
        """view pending domains"""
        data = {
            "domains": models.LinkDomain.objects.filter(status=status)
            .prefetch_related("links")
            .order_by("-created_date"),
            "counts": {
                "pending": models.LinkDomain.objects.filter(status="pending").count(),
                "approved": models.LinkDomain.objects.filter(status="approved").count(),
                "blocked": models.LinkDomain.objects.filter(status="blocked").count(),
            },
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
        return redirect("settings-link-domain", status=status)


@require_POST
@login_required
@permission_required("bookwyrm.moderate_user")
def update_domain_status(request, domain_id, status):
    """This domain seems fine"""
    domain = get_object_or_404(models.LinkDomain, id=domain_id)
    domain.raise_not_editable(request.user)

    domain.status = status
    domain.save()
    return redirect("settings-link-domain", status="pending")
