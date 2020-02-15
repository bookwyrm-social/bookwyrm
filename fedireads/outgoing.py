''' handles all the activity coming out of the server '''
from datetime import datetime
from django.http import HttpResponseNotFound, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import requests
from urllib.parse import urlencode
from uuid import uuid4

from fedireads import models
from fedireads.activity import create_review
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

        path = 'https://%s%s?' % (DOMAIN, request.path)
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
        collection_id = path + urlencode(params)

        messages = models.Activity.objects.filter(
            user=user,
            activity_type__in=['Article', 'Note'],
            **filters
            ).all()[:limit]

        outbox_page = {
            '@context': 'https://www.w3.org/ns/activitystreams',
            'id': collection_id,
            'type': 'OrderedCollectionPage',
            'partOf': 'https://oulipo.social/users/mus/outbox',
            'orderedItems': [m.content for m in messages],
        }
        if max_id:
            outbox_page['next'] = path + \
                urlencode({'min_id': max_id, 'page': 'true'})
        if min_id:
            outbox_page['prev'] = path + \
                urlencode({'max_id': min_id, 'page': 'true'})
        return JsonResponse(outbox_page)

    # collection overview
    size = models.Review.objects.filter(user=user).count()
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
        'id': 'https://%s/%s#accepts/follows/' % (DOMAIN, to_follow.localname),
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
        shelf=shelf,
        book=book,
    ).save()

    broadcast(user, activity, recipients)


def handle_unshelve(user, book, shelf):
    ''' a local user is getting a book put on their shelf '''
    # update the database
    row = models.ShelfBook.objects.get(book=book, shelf=shelf)
    row.delete()

    # send out the activitypub action
    summary = '%s removed %s from %s' % (
        user.username,
        book.data['title'],
        shelf.name
    )

    uuid = uuid4()
    activity = {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': str(uuid),
        'summary': summary,
        'type': 'Remove',
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
        shelf=shelf,
        book=book,
        activity_type='Remove',
    ).save()

    broadcast(user, activity, recipients)


def handle_review(user, book, name, content, rating):
    ''' post a review '''
    # validated and saves the review in the database so it has an id
    review = create_review(user, book, name, content, rating)

    review_path = 'https://%s/user/%s/status/%d' % \
        (DOMAIN, user.localname, review.id)
    book_path = 'https://%s/book/%s' % (DOMAIN, review.book.openlibrary_key)

    review_activity = {
        'id': review_path,
        'url': review_path,
        'inReplyTo': book_path,
        'published': datetime.utcnow().isoformat(),
        'attributedTo': user.actor,
        # TODO: again, assuming all posts are public
        'to': ['https://www.w3.org/ns/activitystreams#Public'],
        'cc': ['https://%s/user/%s/followers' % (DOMAIN, user.localname)],
        'sensitive': False, # TODO: allow content warning/sensitivity
        'content': content,
        'type': 'Note',
        'fedireadsType': 'Review',
        'name': name,
        'rating': rating, # fedireads-only custom field
        'attachment': [], # TODO: the book cover
        'replies': {
            'id': '%s/replies' % review_path,
            'type': 'Collection',
            'first': {
                'type': 'CollectionPage',
                'next': '%s/replies?only_other_accounts=true&page=true' % \
                    review_path,
                'partOf': '%s/replies' % review_path,
                'items': [], # TODO: populate with replies
            }
        }
    }

    activity = {
        '@context': 'https://www.w3.org/ns/activitystreams',

        'id': '%s/activity' % review_path,
        'type': 'Create',
        'actor': user.actor,
        'published': datetime.utcnow().isoformat(),

        'to': ['%s/followers' % user.actor],
        'cc': ['https://www.w3.org/ns/activitystreams#Public'],

        'object': review_activity,
        # TODO: signature
    }

    recipients = get_recipients(user, 'public')
    broadcast(user, activity, recipients)

