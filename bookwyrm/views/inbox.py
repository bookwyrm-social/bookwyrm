''' incoming activities '''
import json
from urllib.parse import urldefrag

from django.http import HttpResponse
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import get_object_or_404
from django.views import View
import requests

from bookwyrm import activitypub, models
from bookwyrm.signatures import Signature


# pylint: disable=no-self-use
class Inbox(View):
    ''' requests sent by outside servers'''
    def post(self, request, username=None):
        ''' only works as POST request '''
        # first let's do some basic checks to see if this is legible
        if username:
            try:
                models.User.objects.get(localname=username)
            except models.User.DoesNotExist:
                return HttpResponseNotFound()

        # is it valid json? does it at least vaguely resemble an activity?
        try:
            resp = request.body
            activity_json = json.loads(resp)
            activity_type = activity_json['type'] # Follow, Accept, Create, etc
        except (json.decoder.JSONDecodeError, KeyError):
            return HttpResponseBadRequest()

        # verify the signature
        if not has_valid_signature(request, activity_json):
            if activity_json['type'] == 'Delete':
                # Pretend that unauth'd deletes succeed. Auth may be failing
                # because the resource or owner of the resource might have
                # been deleted.
                return HttpResponse()
            return HttpResponse(status=401)

        # get the activity dataclass from the type field
        try:
            serializer = getattr(activitypub, activity_type)
            serializer(**activity_json)
        except (AttributeError, activitypub.ActivitySerializerError):
            return HttpResponseNotFound()

        return HttpResponse()


def has_valid_signature(request, activity):
    ''' verify incoming signature '''
    try:
        signature = Signature.parse(request)

        key_actor = urldefrag(signature.key_id).url
        if key_actor != activity.get('actor'):
            raise ValueError("Wrong actor created signature.")

        remote_user = activitypub.resolve_remote_id(models.User, key_actor)
        if not remote_user:
            return False

        try:
            signature.verify(remote_user.key_pair.public_key, request)
        except ValueError:
            old_key = remote_user.key_pair.public_key
            remote_user = activitypub.resolve_remote_id(
                models.User, remote_user.remote_id, refresh=True
            )
            if remote_user.key_pair.public_key == old_key:
                raise # Key unchanged.
            signature.verify(remote_user.key_pair.public_key, request)
    except (ValueError, requests.exceptions.HTTPError):
        return False
    return True
