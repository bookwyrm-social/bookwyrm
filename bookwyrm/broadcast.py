''' send out activitypub messages '''
import json
from django.utils.http import http_date
import requests

from bookwyrm import models
from bookwyrm.activitypub import ActivityEncoder
from bookwyrm.tasks import app
from bookwyrm.signatures import make_signature, make_digest


def get_public_recipients(user, software=None):
    ''' everybody and their public inboxes '''
    followers = user.followers.filter(local=False)
    if software:
        followers = followers.filter(bookwyrm_user=(software == 'bookwyrm'))

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
    if privacy == 'public':
        recipients += get_public_recipients(sender, software=software)
    broadcast_task.delay(
        sender.id,
        json.dumps(activity, cls=ActivityEncoder),
        recipients
    )


@app.task
def broadcast_task(sender_id, activity, recipients):
    ''' the celery task for broadcast '''
    sender = models.User.objects.get(id=sender_id)
    errors = []
    for recipient in recipients:
        try:
            sign_and_send(sender, activity, recipient)
        except requests.exceptions.HTTPError as e:
            errors.append({
                'error': str(e),
                'recipient': recipient,
                'activity': activity,
            })
    return errors


def sign_and_send(sender, data, destination):
    ''' crpyto whatever and http junk '''
    now = http_date()

    if not sender.key_pair.private_key:
        # this shouldn't happen. it would be bad if it happened.
        raise ValueError('No private key found for sender')

    digest = make_digest(data)

    response = requests.post(
        destination,
        data=data,
        headers={
            'Date': now,
            'Digest': digest,
            'Signature': make_signature(sender, destination, now, digest),
            'Content-Type': 'application/activity+json; charset=utf-8',
        },
    )
    if not response.ok:
        response.raise_for_status()
    return response
