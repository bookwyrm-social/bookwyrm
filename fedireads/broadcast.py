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


def get_recipients(user, post_privacy, direct_recipients=None, limit=False):
    ''' deduplicated list of recipient inboxes '''
    # we're always going to broadcast to any direct recipients
    direct_recipients = direct_recipients or []
    recipients = [u.inbox for u in direct_recipients]

    # if we're federating a book, it isn't related to any user's followers, we
    # just want to send it out. To whom? I'm not sure, but for now, everyone.
    if not user:
        users = models.User.objects.filter(local=False).all()
        recipients += list(set(
            u.shared_inbox if u.shared_inbox else u.inbox for u in users
        ))
        return recipients

    if post_privacy == 'direct':
        # all we care about is direct_recipients, not followers, so we're done
        return recipients

    # load all the followers of the user who is sending the message
    # "limit" refers to whether we want to send to other fedireads instances,
    # or to only non-fedireads instances. this is confusing (TODO)
    if not limit:
        followers = user.followers.all()
    else:
        fedireads_user = limit == 'fedireads'
        followers = user.followers.filter(fedireads_user=fedireads_user).all()

    # we don't need to broadcast to ourself
    followers = followers.filter(local=False)

    # TODO I don't think this is actually accomplishing pubic/followers only?
    if post_privacy == 'public':
        # post to public shared inboxes
        shared_inboxes = set(
            u.shared_inbox for u in followers if u.shared_inbox
        )
        recipients += list(shared_inboxes)
        recipients += [u.inbox for u in followers if not u.shared_inbox]

    if post_privacy == 'followers':
        # don't send it to the shared inboxes
        inboxes = set(u.inbox for u in followers)
        recipients += list(inboxes)

    return recipients


def broadcast(sender, activity, recipients):
    ''' send out an event '''
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

