''' handles all the activity coming out of the server '''
from django.http import HttpResponseNotFound, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import requests
from urllib.parse import urlencode
from uuid import uuid4

from fedireads import models
from fedireads.activity import create_review, create_status
from fedireads.activity import get_status_json, get_review_json
from fedireads.activity import get_add_json, get_remove_json, get_create_json
from fedireads.remote_user import get_or_create_remote_user
from fedireads.broadcast import get_recipients, broadcast
from fedireads.settings import DOMAIN


@csrf_exempt
def outbox(request, username):
    ''' outbox for the requested user '''
    user = models.User.objects.get(localname=username)
    if request.method != 'GET':
        return HttpResponseNotFound()

    # paginated list of messages
    if request.GET.get('page'):
        limit = 20
        min_id = request.GET.get('min_id')
        max_id = request.GET.get('max_id')

        query_path = user.outbox + '?'
        # filters for use in the django queryset min/max
        filters = {}
        # params for the outbox page id
        params = {'page': 'true'}
        if min_id != None:
            params['min_id'] = min_id
            filters['id__gt'] = min_id
        if max_id != None:
            params['max_id'] = max_id
            filters['id__lte'] = max_id
        collection_id = query_path + urlencode(params)

        outbox_page = {
            '@context': 'https://www.w3.org/ns/activitystreams',
            'id': collection_id,
            'type': 'OrderedCollectionPage',
            'partOf': user.outbox,
            'orderedItems': [],
        }
        statuses = models.Status.objects.filter(user=user, **filters).all()
        for status in statuses[:limit]:
            outbox_page['orderedItems'].append(get_status_json(status))

        if max_id:
            outbox_page['next'] = query_path + \
                urlencode({'min_id': max_id, 'page': 'true'})
        if min_id:
            outbox_page['prev'] = query_path + \
                urlencode({'max_id': min_id, 'page': 'true'})
        return JsonResponse(outbox_page)

    # collection overview
    size = models.Status.objects.filter(user=user).count()
    return JsonResponse({
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': '%s/outbox' % user.actor,
        'type': 'OrderedCollection',
        'totalItems': size,
        'first': '%s/outbox?page=true' % user.actor,
        'last': '%s/outbox?min_id=0&page=true' % user.actor
    })


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
        'id': 'https://%s/%s' % (DOMAIN, str(uuid)),
        'summary': '',
        'type': 'Follow',
        'actor': user.actor,
        'object': to_follow.actor,
    }

    errors = broadcast(user, activity, [to_follow.inbox])
    for error in errors:
        # TODO: following masto users is returning 400
        raise(error['error'])


def handle_outgoing_accept(user, to_follow, activity):
    ''' send an acceptance message to a follow request '''
    to_follow.followers.add(user)
    activity = {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': '%s#accepts/follows/' % to_follow.absolute_id,
        'type': 'Accept',
        'actor': to_follow.actor,
        'object': activity,
    }
    recipient = get_recipients(
        to_follow,
        'direct',
        direct_recipients=[user]
    )
    broadcast(to_follow, activity, recipient)


def handle_shelve(user, book, shelf):
    ''' a local user is getting a book put on their shelf '''
    # update the database
    # TODO: this should probably happen in incoming instead
    models.ShelfBook(book=book, shelf=shelf, added_by=user).save()

    activity = get_add_json(user, book, shelf)
    recipients = get_recipients(user, 'public')
    broadcast(user, activity, recipients)

    # tell the world about this cool thing that happened
    verb = {
        'to-read': 'wants to read',
        'reading': 'started reading',
        'read': 'finished reading'
    }[shelf.identifier]
    name = user.name if user.name else user.localname
    message = '%s %s %s' % (name, verb, book.data['title'])
    status = create_status(user, message, mention_books=[book])

    activity = get_status_json(status)
    create_activity = get_create_json(user, activity)

    broadcast(user, create_activity, recipients)


def handle_unshelve(user, book, shelf):
    ''' a local user is getting a book put on their shelf '''
    # update the database
    # TODO: this should probably happen in incoming instead
    row = models.ShelfBook.objects.get(book=book, shelf=shelf)
    row.delete()

    activity = get_remove_json(user, book, shelf)
    recipients = get_recipients(user, 'public')

    broadcast(user, activity, recipients)


def handle_review(user, book, name, content, rating):
    ''' post a review '''
    # validated and saves the review in the database so it has an id
    review = create_review(user, book, name, content, rating)

    review_activity = get_review_json(review)
    create_activity = get_create_json(user, review_activity)

    recipients = get_recipients(user, 'public')
    broadcast(user, create_activity, recipients)

