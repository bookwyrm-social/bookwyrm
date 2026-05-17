"""require signed headers and user log in depending on site settings"""

import re
from requests.exceptions import HTTPError

from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required

from bookwyrm.connectors import get_data
from bookwyrm.activitypub import resolve_remote_id
from bookwyrm.models import SiteSettings, User
from bookwyrm.settings import DOMAIN
from bookwyrm.signatures import Signature
from bookwyrm.views.helpers import is_api_request
from bookwyrm.views.inbox import raise_is_blocked_user_agent

require_signed_get = SiteSettings.get().require_signed_get
require_login_everywhere = SiteSettings.get().require_login_everywhere
block_search = SiteSettings.get().block_incoming_search

allowed_views = [
    # basic web utility views
    "robots.txt",
    "manifest.json",
    "^opensearch.xml$",
    # setup views
    "^setup/?$",
    "^setup/admin/?$",
    # login and register
    "^login/?$",
    "^login/(?P<confirmed>confirmed)/?$",
    "^register/?$",
    "confirm-email/?$",
    "confirm-email/(?P<code>[A-Za-z0-9]+)/?$",
    "^resend-link/?$",
    "^invite-request/?$",
    "^invite/(?P<code>[A-Za-z0-9]+)/?$",
    "^2fa-check/?$",
]


class BookWyrmSecurityChecks:
    """lock down incoming access depending on site settings"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.

        # don't secure against yourself
        if request.REMOTE_HOST == DOMAIN:
            return self.get_response(request)

        # block search endpoint if disabled
        if block_search:
            if re.search("^/?search.json/?$", request.path):
                raise PermissionDenied

        if require_signed_get and request.method == "GET" and is_api_request(request):
            # if we disabled federation, disallow all API requests
            # this will include nodeinfo and webfinger etc
            SiteSettings.raise_federation_disabled()

            # check if this server is on our shitlist
            raise_is_blocked_user_agent(request)

            # require signed headers
            if not has_valid_get_signature(request):
                raise PermissionDenied

        elif require_login_everywhere:
            # require login unless endpoint is on the allow list
            if not request.user.is_authenticated:
                for path in allowed_views:
                    if re.search(
                        path, request.path
                    ):  # TODO: does this need a forward slash?
                        return login_required(self.get_response)(request)

        return self.get_response(request)


def has_valid_get_signature(request):
    """verify incoming signature"""
    try:
        signature = Signature.parse(request)
        # TODO: do we make get requests from our own server?

        # have we seen this actor before? It's probably an instance actor
        known_actor = User.objects.filter(key_pair__remote_id=signature.key_id).first()
        if known_actor:
            actor_id = known_actor.id
        else:
            # we have to check the signature.key_id for an owner
            actor_id = get_data(signature.key_id).get("owner")

        # If we don't know this actor we're making a second request back
        # to the requesting server here, but what can you do...
        remote_actor = resolve_remote_id(
            actor_id, model=User, save=False
        )  # don't save the actor yet, the signature might fail

        # if there's no actor we can't check their signature
        if not remote_actor:
            return False

        if signature.key_id != remote_actor.key_pair.remote_id:
            if (
                signature.key_id != f"{remote_actor.remote_id}#main-key"
            ):  # legacy Bookwyrm
                raise ValueError("Wrong actor created signature.")

        try:
            signature.verify_get(remote_actor.key_pair.public_key, request)
        except ValueError:
            old_key = remote_actor.key_pair.public_key
            remote_actor = resolve_remote_id(
                remote_actor.remote_id, model=User, refresh=True, save=False
            )
            if remote_actor.key_pair.public_key == old_key:
                raise  # Key unchanged.
            signature.verify_get(remote_actor.key_pair.public_key, request)
    except (ValueError, HTTPError):
        return False

    # save new actors so we can check our DB next time
    if not remote_actor.id:
        remote_actor.save(broadcast=False)
    return True
