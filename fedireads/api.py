''' api utilties '''
from base64 import b64encode
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from datetime import datetime
import json
import requests

from fedireads import models
from fedireads import incoming
from fedireads.settings import DOMAIN


def get_or_create_remote_user(actor):
    ''' look up a remote user or add them '''
    try:
        return models.User.objects.get(actor=actor)
    except models.User.DoesNotExist:
        pass

    # get the user's info
    response = requests.get(
        actor,
        headers={'Accept': 'application/activity+json'}
    )
    data = response.json()

    username = '%s@%s' % (actor.split('/')[-1], actor.split('/')[2])
    shared_inbox = data.get('endpoints').get('sharedInbox') if \
        data.get('endpoints') else None
    user = models.User.objects.create_user(
        username, '', '',
        name=data.get('name'),
        summary=data.get('summary'),
        inbox=data['inbox'],
        outbox=data['outbox'],
        shared_inbox=shared_inbox,
        public_key=data.get('publicKey').get('publicKeyPem'),
        actor=actor,
        local=False
    )
    return user


def get_recipients(user, post_privacy, direct_recipients=None):
    ''' deduplicated list of recipients '''
    recipients = direct_recipients or []

    followers = user.followers.all()
    if post_privacy == 'public':
        # post to public shared inboxes
        shared_inboxes = set(u.shared_inbox for u in followers)
        recipients += list(shared_inboxes)
        # TODO: not every user has a shared inbox
        # TODO: direct to anyone who's mentioned
    if post_privacy == 'followers':
        # don't send it to the shared inboxes
        inboxes = set(u.inbox for u in followers)
        recipients += list(inboxes)
    # if post privacy is direct, we just have direct recipients,
    # which is already set. hurray
    return recipients


def broadcast(sender, action, recipients):
    ''' send out an event '''
    errors = []
    for recipient in recipients:
        try:
            sign_and_send(sender, action, recipient)
        except requests.exceptions.HTTPError as e:
            errors.append({
                'error': e,
                'recipient': recipient,
                'activity': action,
            })
    return errors


def sign_and_send(sender, action, destination):
    ''' crpyto whatever and http junk '''
    inbox_fragment = sender.inbox.replace('https://%s' % DOMAIN, '')
    now = datetime.utcnow().isoformat()
    signature_headers = [
        '(request-target): post %s' % inbox_fragment,
        'host: https://%s' % DOMAIN,
        'date: %s' %  now
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
    signature = ','.join('%s="%s"' % (k, v) for (k, v) in signature.items())

    response = requests.post(
        destination,
        data=json.dumps(action),
        headers={
            'Date': now,
            'Signature': signature,
            'Host': 'https://%s' % DOMAIN,
            'Content-Type': 'application/activity+json; charset=utf-8',
        },
    )
    if not response.ok:
        response.raise_for_status()
    incoming.handle_response(response)

