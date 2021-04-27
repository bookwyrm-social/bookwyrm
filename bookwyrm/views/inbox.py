""" incoming activities """
import json
import re
from urllib.parse import urldefrag

from django.http import HttpResponse, HttpResponseNotFound
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
import requests

from bookwyrm import activitypub, models
from bookwyrm.tasks import app
from bookwyrm.signatures import Signature
from bookwyrm.utils import regex


@method_decorator(csrf_exempt, name="dispatch")
# pylint: disable=no-self-use
class Inbox(View):
    """requests sent by outside servers"""

    def post(self, request, username=None):
        """only works as POST request"""
        # first check if this server is on our shitlist
        if is_blocked_user_agent(request):
            return HttpResponseForbidden()

        # make sure the user's inbox even exists
        if username:
            try:
                models.User.objects.get(localname=username)
            except models.User.DoesNotExist:
                return HttpResponseNotFound()

        # is it valid json? does it at least vaguely resemble an activity?
        try:
            activity_json = json.loads(request.body)
        except json.decoder.JSONDecodeError:
            return HttpResponseBadRequest()

        # let's be extra sure we didn't block this domain
        if is_blocked_activity(activity_json):
            return HttpResponseForbidden()

        if (
            not "object" in activity_json
            or not "type" in activity_json
            or not activity_json["type"] in activitypub.activity_objects
        ):
            return HttpResponseNotFound()

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


def is_blocked_user_agent(request):
    """check if a request is from a blocked server based on user agent"""
    # check user agent
    user_agent = request.headers.get("User-Agent")
    if not user_agent:
        return False
    url = re.search(r"https?://{:s}/?".format(regex.domain), user_agent)
    if not url:
        return False
    url = url.group()
    return models.FederatedServer.is_blocked(url)


def is_blocked_activity(activity_json):
    """get the sender out of activity json and check if it's blocked"""
    actor = activity_json.get("actor")

    # check if the user is banned/deleted
    existing = models.User.find_existing_by_remote_id(actor)
    if existing and existing.deleted:
        return True

    if not actor:
        # well I guess it's not even a valid activity so who knows
        return False
    return models.FederatedServer.is_blocked(actor)


@app.task
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
