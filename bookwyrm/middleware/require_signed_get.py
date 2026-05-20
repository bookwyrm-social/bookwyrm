"""Require all GET API requests to use signed HTTP headers"""

import re
from requests.exceptions import HTTPError

from django.core.exceptions import PermissionDenied

from bookwyrm.activitypub import resolve_remote_id
from bookwyrm.connectors import get_data
from bookwyrm.models import SiteSettings, User
from bookwyrm.signatures import Signature
from bookwyrm.views.helpers import is_api_request
from bookwyrm.views.inbox import raise_is_blocked_user_agent


class RequireSignedGet:
    """lock down incoming GET API requests"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        """run before next middleware or view"""

        if is_api_request(request):
            # Always check if this server is on our shitlist
            raise_is_blocked_user_agent(request)

            # if we disabled federation, disallow all API requests
            # this will include nodeinfo and webfinger etc
            SiteSettings.raise_federation_disabled()

            if SiteSettings.get().require_signed_get and request.method == "GET":
                allowed_api_views = [
                    r"^/\.well-known/webfinger/?$",
                    r"^/\.well-known/nodeinfo/?$",
                    r"^/\.well-known/host-meta/?$",
                    r"^/nodeinfo/2\.0/?$",
                ]

                # ignore well-known and nodeinfo paths
                # otherwise nobody can follow our users
                for path in allowed_api_views:
                    if re.search(path, request.path):
                        return self.get_response(request)

                # require signed headers for everything else
                if not has_valid_get_signature(request):
                    raise PermissionDenied

        # we're good, continue
        return self.get_response(request)


def has_valid_get_signature(request):
    """verify incoming signature"""
    try:
        signature = Signature.parse(request)
        # have we seen this actor before? It's probably an instance actor
        known_actor = User.objects.filter(key_pair__remote_id=signature.key_id).first()
        if known_actor:
            remote_actor = known_actor
        else:
            # Key id is probably the same as the user endpoint
            remote_actor = resolve_remote_id(signature.key_id, model=User, save=False)

            if not remote_actor:
                # ...but it might not be
                # see https://swicg.github.io/activitypub-http-signature/#how-to-obtain-a-signature-s-public-key
                data = get_data(signature.key_id)

                try:
                    actor_id = data.get("owner")
                except KeyError:
                    actor_id = data.get("controller")

                remote_actor = resolve_remote_id(actor_id, model=User, save=False)

        # well we tried everything I guess
        if not remote_actor:
            return False

        if signature.key_id != remote_actor.key_pair.remote_id:
            if (
                signature.key_id != f"{remote_actor.remote_id}#main-key"
            ):  # legacy Bookwyrm
                raise ValueError("Wrong actor created signature.")

        try:
            signature.verify(
                remote_actor.key_pair.public_key, request, request_type="get"
            )
        except ValueError:
            old_key = remote_actor.key_pair.public_key
            remote_actor = resolve_remote_id(
                remote_actor.remote_id, model=User, refresh=True, save=False
            )
            if not remote_actor:
                return False
            if remote_actor.key_pair.public_key == old_key:
                raise  # Key unchanged.
            signature.verify(
                remote_actor.key_pair.public_key, request, request_type="get"
            )
    except (ValueError, HTTPError):
        return False

    # save previously unknown actors so we can check our DB next time
    if not remote_actor.id:
        remote_actor.save(broadcast=False)
    return True
