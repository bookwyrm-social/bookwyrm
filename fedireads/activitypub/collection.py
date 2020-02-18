''' activitypub json for collections '''
from uuid import uuid4
from urllib.parse import urlencode

from .status import get_status

def get_outbox(user, size):
    ''' helper function for creating an outbox '''
    return get_ordered_collection(user.outbox, size)


def get_outbox_page(user, page_id, statuses, max_id, min_id):
    ''' helper for formatting outbox pages '''
    # not generalizing this more because the format varies for some reason
    page = {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': page_id,
        'type': 'OrderedCollectionPage',
        'partOf': user.outbox,
        'orderedItems': [],
    }

    for status in statuses:
        page['orderedItems'].append(get_status(status))

    if max_id:
        page['next'] = user.outbox + '?' + \
            urlencode({'min_id': max_id, 'page': 'true'})
    if min_id:
        page['prev'] = user.outbox + '?' + \
            urlencode({'max_id': min_id, 'page': 'true'})

    return page


def get_followers(user, page, follow_queryset):
    ''' list of people who follow a user '''
    id_slug = '%s/followers' % user.actor
    return get_follow_info(id_slug, page, follow_queryset)


def get_following(user, page, follow_queryset):
    ''' list of people who follow a user '''
    id_slug = '%s/following' % user.actor
    return get_follow_info(id_slug, page, follow_queryset)


def get_follow_info(id_slug, page, follow_queryset):
    ''' a list of followers or following '''
    if page:
        return get_follow_page(follow_queryset, id_slug, page)
    count = follow_queryset.count()
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': id_slug,
        'type': 'OrderedCollection',
        'totalItems': count,
        'first': '%s?page=1' % id_slug,
    }


# TODO: generalize these pagination functions
def get_follow_page(user_list, id_slug, page):
    ''' format a list of followers/following '''
    page = int(page)
    page_length = 10
    start = (page - 1) * page_length
    end = start + page_length
    follower_page = user_list.all()[start:end]
    data = {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': '%s?page=%d' % (id_slug, page),
        'type': 'OrderedCollectionPage',
        'totalItems': user_list.count(),
        'partOf': id_slug,
        'orderedItems': [u.actor for u in follower_page],
    }
    if end <= user_list.count():
        # there are still more pages
        data['next'] = '%s?page=%d' % (id_slug, page + 1)
    if start > 0:
        data['prev'] = '%s?page=%d' % (id_slug, page - 1)
    return data


def get_ordered_collection(id_slug, size):
    ''' create an ordered collection '''
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': id_slug,
        'type': 'OrderedCollection',
        'totalItems': size,
        'first': '%s?page=true' % id_slug,
        'last': '%s?min_id=0&page=true' % id_slug
    }


def get_add(*args):
    ''' activitypub Add activity '''
    return get_add_remove(*args, action='Add')


def get_remove(*args):
    ''' activitypub Add activity '''
    return get_add_remove(*args, action='Remove')


def get_add_remove(user, book, shelf, action='Add'):
    ''' format an Add or Remove json blob '''
    uuid = uuid4()
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': str(uuid),
        'type': action,
        'actor': user.actor,
        'object': {
            'type': 'Document',
            'name': book.data['title'],
            'url': book.openlibrary_key
        },
        'target': {
            'type': 'Collection',
            'name': shelf.name,
            'id': shelf.absolute_id,
        }
    }


