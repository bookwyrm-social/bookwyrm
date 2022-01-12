""" non-interactive pages """
from django.template.response import TemplateResponse
from django.views import View

from bookwyrm import forms
from bookwyrm.views.feed import Feed


# pylint: disable= no-self-use
class Home(View):
    """landing page or home feed depending on auth"""

    def get(self, request):
        """this is the same as the feed on the home tab"""
        if request.user.is_authenticated:
            feed_view = Feed.as_view()
            return feed_view(request, "home")
        landing_view = Landing.as_view()
        return landing_view(request)


class Landing(View):
    """preview of recently reviewed books"""

    def get(self, request):
        """tiled book activity page"""
        data = {
            "register_form": forms.RegisterForm(),
            "request_form": forms.InviteRequestForm(),
        }
        return TemplateResponse(request, "landing/landing.html", data)
