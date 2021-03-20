""" incoming activities """
import json
from urllib.parse import urldefrag

from django.http import HttpResponse
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
import requests

from bookwyrm import activitypub, models
from bookwyrm.tasks import app
from bookwyrm.signatures import Signature


@method_decorator(csrf_exempt, name="dispatch")
# pylint: disable=no-self-use
class Inbox(View):
    """ requests sent by outside servers"""

    def post(self, request, username=None):
        """ only works as POST request """
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


@app.task
def activity_task(activity_json):
    """ do something with this json we think is legit """
    # lets see if the activitypub module can make sense of this json
    try:
        activity = activitypub.parse(activity_json)
    except activitypub.ActivitySerializerError:
        return

    # cool that worked, now we should do the action described by the type
    # (create, update, delete, etc)
    try:
        activity.action()
    except activitypub.ActivitySerializerError:
        # this is raised if the activity is discarded
        return


def has_valid_signature(request, activity):
    """ verify incoming signature """
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
