''' makin' freinds inthe ap json format '''
from uuid import uuid4

from fedireads.settings import DOMAIN


def get_follow_request(user, to_follow):
    ''' a local user wants to follow someone '''
    uuid = uuid4()
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': 'https://%s/%s' % (DOMAIN, str(uuid)),
        'summary': '',
        'type': 'Follow',
        'actor': user.actor,
        'object': to_follow.actor,
    }

def get_unfollow(relationship):
    ''' undo that precious bond of friendship '''
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': '%s/undo' % relationship.absolute_id,
        'type': 'Undo',
        'actor': relationship.user_subject.actor,
        'object': {
            'id': relationship.relationship_id,
            'type': 'Follow',
            'actor': relationship.user_subject.actor,
            'object': relationship.user_object.actor,
        }
    }


def get_accept(user, relationship):
    ''' accept a follow request '''
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': '%s#accepts/follows/' % user.absolute_id,
        'type': 'Accept',
        'actor': user.actor,
        'object': {
            'id': relationship.relationship_id,
            'type': 'Follow',
            'actor': relationship.user_subject.actor,
            'object': relationship.user_object.actor,
        }
    }


def get_reject(user, relationship):
    ''' reject a follow request '''
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': '%s#rejects/follows/' % user.absolute_id,
        'type': 'Reject',
        'actor': user.actor,
        'object': {
            'id': relationship.relationship_id,
            'type': 'Follow',
            'actor': relationship.user_subject.actor,
            'object': relationship.user_object.actor,
        }
    }


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
