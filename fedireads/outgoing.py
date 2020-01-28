''' handles all the activity coming out of the server '''
from datetime import datetime
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import requests
from uuid import uuid4

from fedireads import models
from fedireads.api import get_or_create_remote_user, get_recipients, \
        broadcast


@csrf_exempt
def outbox(request, username):
    ''' outbox for the requested user '''
    user = models.User.objects.get(localname=username)
    size = models.Review.objects.filter(user=user).count()
    if request.method == 'GET':
        # list of activities
        return JsonResponse({
            '@context': 'https://www.w3.org/ns/activitystreams',
            'id': '%s/outbox' % user.actor,
            'type': 'OrderedCollection',
            'totalItems': size,
            'first': '%s/outbox?page=true' % user.actor,
            'last': '%s/outbox?min_id=0&page=true' % user.actor
        })
    # TODO: paginated list of messages

    #data = request.body.decode('utf-8')
    return HttpResponse()


def handle_account_search(query):
    ''' webfingerin' other servers '''
    user = None
    domain = query.split('@')[1]
    try:
        user = models.User.objects.get(username=query)
    except models.User.DoesNotExist:
        url = 'https://%s/.well-known/webfinger?resource=acct:%s' % \
            (domain, query)
        response = requests.get(url)
        if not response.ok:
            response.raise_for_status()
        data = response.json()
        for link in data['links']:
            if link['rel'] == 'self':
                user = get_or_create_remote_user(link['href'])
    return user


def handle_outgoing_follow(user, to_follow):
    ''' someone local wants to follow someone '''
    uuid = uuid4()
    activity = {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': str(uuid),
        'summary': '',
        'type': 'Follow',
        'actor': user.actor,
        'object': to_follow.actor,
    }

    broadcast(user, activity, [to_follow.inbox])


def handle_shelve(user, book, shelf):
    ''' a local user is getting a book put on their shelf '''
    # update the database
    models.ShelfBook(book=book, shelf=shelf, added_by=user).save()

    # send out the activitypub action
    summary = '%s marked %s as %s' % (
        user.username,
        book.data['title'],
        shelf.name
    )

    uuid = uuid4()
    activity = {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': str(uuid),
        'summary': summary,
        'type': 'Add',
        'actor': user.actor,
        'object': {
            'type': 'Document',
            'name': book.data['title'],
            'url': book.openlibrary_key
        },
        'target': {
            'type': 'Collection',
            'name': shelf.name,
            'id': shelf.activitypub_id
        }
    }
    recipients = get_recipients(user, 'public')

    models.ShelveActivity(
        uuid=uuid,
        user=user,
        content=activity,
        activity_type='Add',
        shelf=shelf,
        book=book,
    ).save()

    broadcast(user, activity, recipients)


def handle_review(user, book, name, content, rating):
    ''' post a review '''
    review_uuid = uuid4()
    obj = {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': str(review_uuid),
        'type': 'Article',
        'published': datetime.utcnow().isoformat(),
        'attributedTo': user.actor,
        'content': content,
        'inReplyTo': book.openlibrary_key,
        'rating': rating, # fedireads-only custom field
        'to': 'https://www.w3.org/ns/activitystreams#Public'
    }
    recipients = get_recipients(user, 'public')
    create_uuid = uuid4()
    activity = {
        '@context': 'https://www.w3.org/ns/activitystreams',

        'id': str(create_uuid),
        'type': 'Create',
        'actor': user.actor,

        'to': ['%s/followers' % user.actor],
        'cc': ['https://www.w3.org/ns/activitystreams#Public'],

        'object': obj,
    }

    models.Review(
        uuid=create_uuid,
        user=user,
        content=activity,
        activity_type='Article',
        book=book,
        work=book.works.first(),
        name=name,
        rating=rating,
        review_content=content,
    ).save()
    broadcast(user, activity, recipients)

