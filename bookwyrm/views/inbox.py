""" incoming activities """
import json
import re
import logging

from urllib.parse import urldefrag
import requests

from django.http import HttpResponse, Http404
from django.core.exceptions import BadRequest, PermissionDenied
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from bookwyrm import activitypub, models
from bookwyrm.tasks import app
from bookwyrm.signatures import Signature
from bookwyrm.utils import regex

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
# pylint: disable=no-self-use
class Inbox(View):
    """requests sent by outside servers"""

    def post(self, request, username=None):
        """only works as POST request"""
        # first check if this server is on our shitlist
        raise_is_blocked_user_agent(request)

        # make sure the user's inbox even exists
        if username:
            get_object_or_404(models.User, localname=username, is_active=True)

        # is it valid json? does it at least vaguely resemble an activity?
        try:
            activity_json = json.loads(request.body)
        except json.decoder.JSONDecodeError:
            raise BadRequest()

        # let's be extra sure we didn't block this domain
        raise_is_blocked_activity(activity_json)

        if (
            not "object" in activity_json
            or not "type" in activity_json
            or not activity_json["type"] in activitypub.activity_objects
        ):
            raise Http404()

        # verify the signature
        if not has_valid_signature(request, activity_json):
            if activity_json["type"] == "Delete":
                # Pretend that unauth'd deletes succeed. Auth may be failing
                # because the resource or owner of the resource might have
                # been deleted.
                return HttpResponse()
            return HttpResponse(status=401)

        activity_task.delay(activity_json)
        return HttpResponse()


def raise_is_blocked_user_agent(request):
    """check if a request is from a blocked server based on user agent"""
    # check user agent
    user_agent = request.headers.get("User-Agent")
    if not user_agent:
        return
    url = re.search(rf"https?://{regex.DOMAIN}/?", user_agent)
    if not url:
        return
    url = url.group()
    if models.FederatedServer.is_blocked(url):
        logger.debug("%s is blocked, denying request based on user agent", url)
        raise PermissionDenied()


def raise_is_blocked_activity(activity_json):
    """get the sender out of activity json and check if it's blocked"""
    actor = activity_json.get("actor")

    if not actor:
        # well I guess it's not even a valid activity so who knows
        return

    # check if the user is banned/deleted
    existing = models.User.find_existing_by_remote_id(actor)
    if existing and existing.deleted:
        logger.debug("%s is banned/deleted, denying request based on actor", actor)
        raise PermissionDenied()

    if models.FederatedServer.is_blocked(actor):
        logger.debug("%s is blocked, denying request based on actor", actor)
        raise PermissionDenied()


@app.task(queue="medium_priority")
def activity_task(activity_json):
    """do something with this json we think is legit"""
    # lets see if the activitypub module can make sense of this json
    activity = activitypub.parse(activity_json)

    # cool that worked, now we should do the action described by the type
    # (create, update, delete, etc)
    activity.action()


def has_valid_signature(request, activity):
    """verify incoming signature"""
    try:
        signature = Signature.parse(request)

        key_actor = urldefrag(signature.key_id).url
        if key_actor != activity.get("actor"):
            raise ValueError("Wrong actor created signature.")

        remote_user = activitypub.resolve_remote_id(key_actor, model=models.User)
        if not remote_user:
            return False

        try:
            signature.verify(remote_user.key_pair.public_key, request)
        except ValueError:
            old_key = remote_user.key_pair.public_key
            remote_user = activitypub.resolve_remote_id(
                remote_user.remote_id, model=models.User, refresh=True
            )
            if remote_user.key_pair.public_key == old_key:
                raise  # Key unchanged.
            signature.verify(remote_user.key_pair.public_key, request)
    except (ValueError, requests.exceptions.HTTPError):
        return False
    return True
