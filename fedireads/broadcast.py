''' send out activitypub messages '''
from base64 import b64encode
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from django.utils.http import http_date
import json
import requests
from urllib.parse import urlparse


def get_recipients(user, post_privacy, direct_recipients=None):
    ''' deduplicated list of recipient inboxes '''
    recipients = direct_recipients or []
    if post_privacy == 'direct':
        # all we care about is direct_recipients, not followers
        return [u.inbox for u in recipients]

    # load all the followers of the user who is sending the message
    followers = user.followers.all()
    if post_privacy == 'public':
        # post to public shared inboxes
        shared_inboxes = set(
            u.shared_inbox for u in followers if u.shared_inbox
        )
        recipients += list(shared_inboxes)
        recipients += [u.inbox for u in followers if not u.shared_inbox]
        # TODO: direct to anyone who's mentioned
    if post_privacy == 'followers':
        # don't send it to the shared inboxes
        inboxes = set(u.inbox for u in followers)
        recipients += list(inboxes)
    return recipients


def broadcast(sender, activity, recipients):
    ''' send out an event '''
    errors = []
    for recipient in recipients:
        try:
            response = sign_and_send(sender, activity, recipient)
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

