''' manage remote users '''
from urllib.parse import urlparse
from uuid import uuid4
import requests

from django.core.files.base import ContentFile
from django.db import transaction

from fedireads import models
from fedireads.status import create_review_from_activity


def get_or_create_remote_user(actor):
    ''' look up a remote user or add them '''
    try:
        return models.User.objects.get(remote_id=actor)
    except models.User.DoesNotExist:
        pass

    # load the user's info from the actor url
    response = requests.get(
        actor,
        headers={'Accept': 'application/activity+json'}
    )
    if not response.ok:
        response.raise_for_status()
    data = response.json()

    actor_parts = urlparse(actor)
    with transaction.atomic():
        user = create_remote_user(data)
        user.federated_server = get_or_create_remote_server(actor_parts.netloc)
        user.save()

    avatar = get_avatar(data)
    user.avatar.save(*avatar)

    if user.fedireads_user:
        get_remote_reviews(user)
    return user


def create_remote_user(data):
    ''' parse the activitypub actor data into a user '''
    actor = data.get('id')
    actor_parts = urlparse(actor)

    # the webfinger format for the username.
    username = '%s@%s' % (actor_parts.path.split('/')[-1], actor_parts.netloc)

    shared_inbox = data.get('endpoints').get('sharedInbox') if \
        data.get('endpoints') else None

    # throws a key error if it can't find any of these fields
    return models.User.objects.create_user(
        username,
        '', '', # email and passwords are left blank
        remote_id=actor,
        name=data.get('name'),
        summary=data.get('summary'),
        inbox=data['inbox'], #fail if there's no inbox
        outbox=data['outbox'], # fail if there's no outbox
        shared_inbox=shared_inbox,
        public_key=data.get('publicKey').get('publicKeyPem'),
        local=False,
        fedireads_user=data.get('fedireadsUser', False),
        manually_approves_followers=data.get(
            'manuallyApprovesFollowers', False),
    )


def get_avatar(data):
    ''' find the icon attachment and load the image from the remote sever '''
    icon_blob = data.get('icon')
    if not icon_blob or not icon_blob.get('url'):
        return None

    response = requests.get(icon_blob['url'])
    if not response.ok:
        return None

    image_name = str(uuid4()) + '.' + icon_blob['url'].split('.')[-1]
    image_content = ContentFile(response.content)
    return [image_name, image_content]


def get_remote_reviews(user):
    ''' ingest reviews by a new remote fedireads user '''
    outbox_page = user.outbox + '?page=true'
    response = requests.get(
        outbox_page,
        headers={'Accept': 'application/activity+json'}
    )
    data = response.json()
    # TODO: pagination?
    for status in data['orderedItems']:
        if status.get('fedireadsType') == 'Review':
            create_review_from_activity(user, status)


def get_or_create_remote_server(domain):
    ''' get info on a remote server '''
    try:
        return models.FederatedServer.objects.get(
            server_name=domain
        )
    except models.FederatedServer.DoesNotExist:
        pass

    response = requests.get(
        'https://%s/.well-known/nodeinfo' % domain,
        headers={'Accept': 'application/activity+json'}
    )
    data = response.json()
    try:
        nodeinfo_url = data.get('links')[0].get('href')
    except (TypeError, KeyError):
        return None

    response = requests.get(
        nodeinfo_url,
        headers={'Accept': 'application/activity+json'}
    )
    data = response.json()

    server = models.FederatedServer.objects.create(
        server_name=domain,
        application_type=data['software']['name'],
        application_version=data['software']['version'],
    )
    return server
