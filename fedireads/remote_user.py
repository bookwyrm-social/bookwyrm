''' manage remote users '''
from urllib.parse import urlparse
from uuid import uuid4
import requests

from django.core.files.base import ContentFile
from django.db import transaction

from fedireads import activitypub, models
from fedireads.status import create_review_from_activity


def get_or_create_remote_user(actor):
    ''' look up a remote user or add them '''
    try:
        return models.User.objects.get(remote_id=actor)
    except models.User.DoesNotExist:
        pass

    data = fetch_user_data(actor)

    actor_parts = urlparse(actor)
    with transaction.atomic():
        user = create_remote_user(data)
        user.federated_server = get_or_create_remote_server(actor_parts.netloc)
        user.save()

    avatar = get_avatar(data)
    if avatar:
        user.avatar.save(*avatar)

    if user.fedireads_user:
        get_remote_reviews(user)
    return user

def fetch_user_data(actor):
    # load the user's info from the actor url
    response = requests.get(
        actor,
        headers={'Accept': 'application/activity+json'}
    )
    if not response.ok:
        response.raise_for_status()
    data = response.json()

    # make sure our actor is who they say they are
    if actor != data['id']:
        raise ValueError("Remote actor id must match url.")
    return data


def create_remote_user(data):
    ''' parse the activitypub actor data into a user '''
    actor = activitypub.Person(**data)

    # the webfinger format for the username.
    actor_parts = urlparse(actor.id)
    username = '%s@%s' % (actor.preferredUsername, actor_parts.netloc)

    return models.User.objects.create_user(
        username,
        '', '', # email and passwords are left blank
        remote_id=actor.id,
        name=actor.name,
        summary=actor.summary,
        inbox=actor.inbox,
        outbox=actor.outbox,
        shared_inbox=actor.endpoints['sharedInbox'],
        public_key=actor.publicKey['publicKeyPem'],
        local=False,
        fedireads_user=actor.fedireadsUser,
        manually_approves_followers=actor.manuallyApprovesFollowers,
    )

def refresh_remote_user(user):
    data = fetch_user_data(user.remote_id)

    shared_inbox = data.get('endpoints').get('sharedInbox') if \
        data.get('endpoints') else None

    # TODO - I think dataclasses change will mean less repetition here later.
    user.name = data.get('name')
    user.summary = data.get('summary')
    user.inbox = data['inbox'] #fail if there's no inbox
    user.outbox = data['outbox'] # fail if there's no outbox
    user.shared_inbox = shared_inbox
    user.public_key = data.get('publicKey').get('publicKeyPem')
    user.local = False
    user.fedireads_user = data.get('fedireadsUser', False)
    user.manually_approves_followers = data.get(
        'manuallyApprovesFollowers', False)
    user.save()

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

    if response.status_code != 200:
        return None

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
