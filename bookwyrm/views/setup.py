""" Installation wizard 🧙 """
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.views import View

from bookwyrm import forms, models


# pylint: disable= no-self-use
class CreateAdmin(View):
    """manage things like the instance name"""

    def get(self, request):
        """Create admin user"""
        # only allow this view when an instance is being installed
        site = models.SiteSettings.objects.get()
        if not site.install_mode:
            raise PermissionDenied()

        data = {
            "register_form": forms.RegisterForm()
        }
        return TemplateResponse(request, "setup/admin.html", data)
