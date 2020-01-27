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

    activity = request.POST.dict()
    if activity['type'] == 'Add':
        handle_add(activity)

    return HttpResponse()

def handle_add(activity):
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
            data=action,
            headers={
                'Date': now,
                'Signature': signature,
                'Host': DOMAIN,
                'Content-Type': 'application/json',
            },
        )
        if not response.ok:
            return response.raise_for_status()

def handle_follow(data):
    pass

def get_or_create_remote_user(activity):
    pass


