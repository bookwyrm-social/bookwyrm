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
        user = models.User.objects.get(actor=actor)
    except models.User.DoesNotExist:
        # TODO: how do you actually correctly learn this?
        username = '%s@%s' % (actor.split('/')[-1], actor.split('/')[2])
        user = models.User.objects.create_user(
            username,
            '', '',
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
    for recipient in recipients:
        # TODO: error handling
        sign_and_send(sender, action, recipient)


def sign_and_send(sender, action, destination):
    ''' crpyto whatever and http junk '''
    inbox_fragment = sender.inbox.replace('https://%s' % DOMAIN, '')
    now = datetime.utcnow().isoformat()
    message_to_sign = '''(request-target): post %s
host: https://%s
date: %s''' % (inbox_fragment, DOMAIN, now)
    signer = pkcs1_15.new(RSA.import_key(sender.private_key))
    signed_message = signer.sign(SHA256.new(message_to_sign.encode('utf8')))

    signature = 'keyId="%s",' % sender.localname
    signature += 'headers="(request-target) host date",'
    signature += 'signature="%s"' % b64encode(signed_message)
    response = requests.post(
        destination,
        data=json.dumps(action),
        headers={
            'Date': now,
            'Signature': signature,
            'Host': DOMAIN,
        },
    )
    if not response.ok:
        response.raise_for_status()
    incoming.handle_response(response)

