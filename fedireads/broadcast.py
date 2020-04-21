''' send out activitypub messages '''
from base64 import b64encode
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from django.utils.http import http_date
import json
import requests
from urllib.parse import urlparse

from fedireads import models
from fedireads.tasks import app


def get_public_recipients(user, software=None):
    ''' everybody and their public inboxes '''
    followers = user.followers.filter(local=False)
    if software:
        # TODO: eventually we may want to handle particular software differently
        followers = followers.filter(fedireads_user=(software == 'fedireads'))

    shared = followers.filter(
        shared_inbox__isnull=False
    ).values_list('shared_inbox', flat=True).distinct()

    inboxes = followers.filter(
        shared_inbox__isnull=True
    ).values_list('inbox', flat=True)

    return list(shared) + list(inboxes)


def broadcast(sender, activity, software=None, \
              privacy='public', direct_recipients=None):
    ''' send out an event '''
    recipients = [u.inbox for u in direct_recipients or []]
    # TODO: other kinds of privacy
    if privacy == 'public':
        recipients = get_public_recipients(sender, software=software)
    broadcast_task.delay(sender.id, activity, recipients)


@app.task
def broadcast_task(sender_id, activity, recipients):
    ''' the celery task for broadcast '''
    sender = models.User.objects.get(id=sender_id)
    errors = []
    for recipient in recipients:
        try:
            sign_and_send(sender, activity, recipient)
        except requests.exceptions.HTTPError as e:
            # TODO: maybe keep track of users who cause errors
            errors.append({
                'error': e,
                'recipient': recipient,
                'activity': activity,
            })
    return errors


def sign_and_send(sender, activity, destination):
    ''' crpyto whatever and http junk '''
    inbox_parts = urlparse(destination)
    now = http_date()
    signature_headers = [
        '(request-target): post %s' % inbox_parts.path,
        'host: %s' % inbox_parts.netloc,
        'date: %s' % now
    ]
    message_to_sign = '\n'.join(signature_headers)

    # TODO: raise an error if the user doesn't have a private key
    signer = pkcs1_15.new(RSA.import_key(sender.private_key))
    signed_message = signer.sign(SHA256.new(message_to_sign.encode('utf8')))

    signature = {
        'keyId': '%s#main-key' % sender.actor,
        'algorithm': 'rsa-sha256',
        'headers': '(request-target) host date',
        'signature': b64encode(signed_message).decode('utf8'),
    }
    signature = ','.join('%s="%s"' % (k, v) for (k, v) in signature.items())

    response = requests.post(
        destination,
        data=json.dumps(activity),
        headers={
            'Date': now,
            'Signature': signature,
            'Content-Type': 'application/activity+json; charset=utf-8',
        },
    )
    if not response.ok:
        response.raise_for_status()
    return response

