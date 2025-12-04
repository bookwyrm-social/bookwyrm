"""big picture settings about how the instance shares data"""

from django.contrib.auth.decorators import login_required, permission_required
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms, models


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.control_federation", raise_exception=True),
    name="dispatch",
)
class FederationSettings(View):
    """what servers do we federate with"""

    def get(self, request):
        """show the current settings"""
        site = models.SiteSettings.get()
        data = {
            "form": forms.FederationSettings(instance=site),
        }
        return TemplateResponse(request, "settings/federation/settings.html", data)

    def post(self, request):
        """Update federation settings"""
        site = models.SiteSettings.get()
        form = forms.FederationSettings(request.POST, instance=site)
        if not form.is_valid():
            data = {"form": form}
            return TemplateResponse(request, "settings/federation/settings.html", data)
        form.save(request)
        data = {"form": forms.FederationSettings(instance=site), "success": True}
        return TemplateResponse(request, "settings/federation/settings.html", data)
