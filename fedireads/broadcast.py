''' send out activitypub messages '''
import json
from urllib.parse import urlparse
from base64 import b64encode
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from django.utils.http import http_date
import requests

from fedireads import models
from fedireads.tasks import app


def get_public_recipients(user, software=None):
    ''' everybody and their public inboxes '''
    followers = user.followers.filter(local=False)
    if software:
        # TODO: eventually we may want to handle particular software differently
        followers = followers.filter(fedireads_user=(software == 'fedireads'))

    # we want shared inboxes when available
    shared = followers.filter(
        shared_inbox__isnull=False
    ).values_list('shared_inbox', flat=True).distinct()

    # if a user doesn't have a shared inbox, we need their personal inbox
    # iirc pixelfed doesn't have shared inboxes
    inboxes = followers.filter(
        shared_inbox__isnull=True
    ).values_list('inbox', flat=True)

    return list(shared) + list(inboxes)


def broadcast(sender, activity, software=None, \
              privacy='public', direct_recipients=None):
    ''' send out an event '''
    # start with parsing the direct recipients
    recipients = [u.inbox for u in direct_recipients or []]
    # and then add any other recipients
    # TODO: other kinds of privacy
    if privacy == 'public':
        recipients += get_public_recipients(sender, software=software)
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


def make_signature(sender, destination, date):
    inbox_parts = urlparse(destination)
    signature_headers = [
        '(request-target): post %s' % inbox_parts.path,
        'host: %s' % inbox_parts.netloc,
        'date: %s' % date,
    ]
    message_to_sign = '\n'.join(signature_headers)
    signer = pkcs1_15.new(RSA.import_key(sender.private_key))
    signed_message = signer.sign(SHA256.new(message_to_sign.encode('utf8')))
    signature = {
        'keyId': '%s#main-key' % sender.actor,
        'algorithm': 'rsa-sha256',
        'headers': '(request-target) host date',
        'signature': b64encode(signed_message).decode('utf8'),
    }
    return ','.join('%s="%s"' % (k, v) for (k, v) in signature.items())

def sign_and_send(sender, activity, destination):
    ''' crpyto whatever and http junk '''
    now = http_date()

    if not sender.private_key:
        # this shouldn't happen. it would be bad if it happened.
        raise ValueError('No private key found for sender')

    response = requests.post(
        destination,
        data=json.dumps(activity),
        headers={
            'Date': now,
            'Signature': make_signature(sender, destination, now),
            'Content-Type': 'application/activity+json; charset=utf-8',
        },
    )
    if not response.ok:
        response.raise_for_status()
    return response
