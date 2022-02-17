""" Installation wizard 🧙 """
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import emailing, forms, models


# pylint: disable= no-self-use
class CreateAdmin(View):
    """manage things like the instance name"""

    def get(self, request):
        """Create admin user"""
        data = {
            "register_form": forms.RegisterForm()
        }
        return TemplateResponse(request, "setup/admin.html", data)
