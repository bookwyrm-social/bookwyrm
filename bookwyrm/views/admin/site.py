""" manage site settings """
from django.contrib.auth.decorators import login_required, permission_required
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms, models


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_instance_settings", raise_exception=True),
    name="dispatch",
)
class Site(View):
    """manage things like the instance name"""

    def get(self, request):
        """edit form"""
        site = models.SiteSettings.objects.get()
        data = {"site_form": forms.SiteForm(instance=site)}
        return TemplateResponse(request, "settings/site.html", data)

    def post(self, request):
        """edit the site settings"""
        site = models.SiteSettings.objects.get()
        form = forms.SiteForm(request.POST, request.FILES, instance=site)
        if not form.is_valid():
            data = {"site_form": form}
            return TemplateResponse(request, "settings/site.html", data)
        site = form.save(request)

        data = {"site_form": forms.SiteForm(instance=site), "success": True}
        return TemplateResponse(request, "settings/site.html", data)
