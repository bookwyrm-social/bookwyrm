''' manage remote users '''
from urllib.parse import urlparse
import requests

from django.db import transaction

from bookwyrm import activitypub, models
from bookwyrm import status as status_builder
from bookwyrm.tasks import app


def get_or_create_remote_user(actor):
    ''' look up a remote user or add them '''
    try:
        return models.User.objects.get(remote_id=actor)
    except models.User.DoesNotExist:
        pass

    actor_parts = urlparse(actor)
    with transaction.atomic():
        user = activitypub.resolve_remote_id(models.User, actor)
        user.federated_server = get_or_create_remote_server(actor_parts.netloc)
        user.save()
    if user.bookwyrm_user:
        get_remote_reviews.delay(user.id)
    return user


def refresh_remote_user(user):
    ''' get updated user data from its home instance '''
    activitypub.resolve_remote_id(user.remote_id, refresh=True)


@app.task
def get_remote_reviews(user_id):
    ''' ingest reviews by a new remote bookwyrm user '''
    try:
        user = models.User.objects.get(id=user_id)
    except models.User.DoesNotExist:
        return
    outbox_page = user.outbox + '?page=true'
    response = requests.get(
        outbox_page,
        headers={'Accept': 'application/activity+json'}
    )
    data = response.json()
    # TODO: pagination?
    for activity in data['orderedItems']:
        status_builder.create_status(activity)


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
