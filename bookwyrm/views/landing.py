""" non-interactive pages """
from django.template.response import TemplateResponse
from django.views import View

from bookwyrm import forms
from .feed import Feed
from . import helpers


# pylint: disable= no-self-use
class About(View):
    """create invites"""

    def get(self, request):
        """more information about the instance"""
        return TemplateResponse(request, "discover/about.html")


class Home(View):
    """discover page or home feed depending on auth"""

    def get(self, request):
        """this is the same as the feed on the home tab"""
        if request.user.is_authenticated:
            feed_view = Feed.as_view()
            return feed_view(request, "home")
        discover_view = Discover.as_view()
        return discover_view(request)


class Discover(View):
    """preview of recently reviewed books"""

    def get(self, request):
        """tiled book activity page"""
        data = {
            "register_form": forms.RegisterForm(),
            "request_form": forms.InviteRequestForm(),
            "books": helpers.get_discover_books(),
        }
        return TemplateResponse(request, "discover/discover.html", data)
