"""require signed headers and user log in depending on site settings"""

import re

from django.contrib.auth.decorators import login_required

from bookwyrm.models import SiteSettings
from bookwyrm.views.helpers import is_api_request

allowed_views = [
    # basic web utility views
    r"/robots.txt",
    r"/manifest.json",
    r"^/opensearch.xml$",
    # site basics
    r"^/?$",
    r"^/about/?$",
    r"^/privacy/?$",
    r"^/conduct/?$",
    # setup
    r"^/setup/?$",
    r"^/setup/admin/?$",
    # login and register
    r"^/login/?$",
    r"^/login/(?P<confirmed>confirmed)/?$",
    r"^/register/?$",
    r"^/password-reset/?$",
    r"/confirm-email/?$",
    r"/confirm-email/(?P<code>[A-Za-z0-9]+)/?$",
    r"^/resend-link/?$",
    r"^/invite/(?P<code>[A-Za-z0-9]+)/?$",
    r"^/2fa-check/?$",
]


class RequireLoginNearlyEverywhere:
    """lock down access depending on site settings"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        """run before next middleware or view"""

        if SiteSettings.get().require_login_nearly_everywhere and not is_api_request(
            request
        ):
            # require login unless endpoint is on the allow list
            if not request.user.is_authenticated:
                for path in allowed_views:
                    if re.search(path, request.path):
                        return self.get_response(request)
                return login_required(self.get_response)(request)

        # we're good, continue
        return self.get_response(request)
