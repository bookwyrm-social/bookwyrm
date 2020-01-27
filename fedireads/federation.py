''' activitystream api '''
from base64 import b64encode
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from datetime import datetime
from django.http import HttpResponse, HttpResponseBadRequest, \
    HttpResponseNotFound, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from fedireads.settings import DOMAIN
from fedireads import models
from fedireads import openlibrary
import fedireads.activitypub_templates as templates
import json
import requests

def webfinger(request):
    ''' allow other servers to ask about a user '''
    resource = request.GET.get('resource')
    if not resource and not resource.startswith('acct:'):
        return HttpResponseBadRequest()
    ap_id = resource.replace('acct:', '')
    user = models.User.objects.filter(activitypub_id=ap_id).first()
    if not user:
        return HttpResponseNotFound('No account found')
    return JsonResponse(format_webfinger(user))


def format_webfinger(user):
    ''' helper function to create structured webfinger json '''
    return {
        'subject': 'acct:%s' % (user.activitypub_id),
        'links': [
            {
                'rel': 'self',
                'type': 'application/activity+json',
                'href': user.actor['id']
            }
        ]
    }


@csrf_exempt
def actor(request, username):
    ''' return an activitypub actor object '''
    user = models.User.objects.get(username=username)
    return JsonResponse(user.actor)


@csrf_exempt
def inbox(request, username):
    ''' incoming activitypub events '''
    if request.method == 'GET':
        # return a collection of something?
        pass

    activity = json.loads(request.body)
    if activity['type'] == 'Add':
        handle_add(activity)

    if activity['type'] == 'Follow':
        response = handle_follow(activity)
        return JsonResponse(response)

    return HttpResponse()

def handle_add(activity):
    ''' adding a book to a shelf '''
    book_id = activity['object']['url']
    book = openlibrary.get_or_create_book(book_id)
    user_ap_id = activity['actor'].replace('https//:', '')
    user = models.User.objects.get(activitypub_id=user_ap_id)
    shelf = models.Shelf.objects.get(activitypub_id=activity['target']['id'])
    models.ShelfBook(
        shelf=shelf,
        book=book,
        added_by=user,
    ).save()


def handle_follow(activity):
    '''
    {
	"@context": "https://www.w3.org/ns/activitystreams",
	"id": "https://friend.camp/768222ce-a1c7-479c-a544-c93b8b67fb54",
	"type": "Follow",
	"actor": "https://friend.camp/users/tripofmice",
	"object": "https://ff2cb3e9.ngrok.io/api/u/mouse"
    }
    '''
    # figure out who they want to follow
    following = activity['object'].replace('https://%s/api/u/' % DOMAIN, '')
    following = models.User.objects.get(username=following)
    # figure out who they are
    ap_id = activity['actor']
    try:
        user = models.User.objects.get(activitypub_id=ap_id)
    except models.User.DoesNotExist:
        user = models.User(activitypub_id=ap_id, local=False).save()
    following.followers.add(user)
    # accept the request
    return templates.accept_follow(activity, following)


@csrf_exempt
def outbox(request, username):
    user = models.User.objects.get(username=username)
    if request.method == 'GET':
        # list of activities
        return JsonResponse()

    data = request.body.decode('utf-8')
    if data.activity.type == 'Follow':
        handle_follow(data)
    return HttpResponse()


def broadcast_action(sender, action, recipients):
    ''' sign and send out the actions '''
    #models.Message(
    #    author=sender,
    #    content=action
    #).save()
    for recipient in recipients:
        action['to'] = 'https://www.w3.org/ns/activitystreams#Public'
        action['cc'] = [recipient]

        inbox_fragment = sender.actor['inbox'].replace('https://' + DOMAIN, '')
        now = datetime.utcnow().isoformat()
        message_to_sign = '''(request-target): post %s
host: https://%s
date: %s''' % (inbox_fragment, DOMAIN, now)
        signer = pkcs1_15.new(RSA.import_key(sender.private_key))
        signed_message = signer.sign(SHA256.new(message_to_sign.encode('utf8')))

        signature = 'keyId="%s",' % sender.activitypub_id
        signature += 'headers="(request-target) host date",'
        signature += 'signature="%s"' % b64encode(signed_message)
        response = requests.post(
            recipient,
            body=action,
            headers={
                'Date': now,
                'Signature': signature,
                'Host': DOMAIN,
            },
        )
        if not response.ok:
            return response.raise_for_status()


def get_or_create_remote_user(activity):
    pass


