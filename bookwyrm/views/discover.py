""" What's up locally """
from django.contrib.auth.decorators import login_required
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms
from . import helpers


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class Discover(View):
    """preview of recently reviewed books"""

    def get(self, request):
        """tiled book activity page"""
        data = {
            "register_form": forms.RegisterForm(),
            "request_form": forms.InviteRequestForm(),
            "books": helpers.get_landing_books(),
        }
        return TemplateResponse(request, "landing/landing.html", data)
