''' status serializers '''
from uuid import uuid4



def get_rating_note(review):
    ''' simple rating, send it as a note not an artciel '''
    status = review.to_activity()
    status['content'] = 'Rated "%s": %d stars' % (
        review.book.title,
        review.rating,
    )
    status['type'] = 'Note'
    return status


def get_replies(status, replies):
    ''' collection of replies '''
    id_slug = status.remote_id + '/replies'
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': id_slug,
        'type': 'Collection',
        'first': {
            'id': '%s?page=true' % id_slug,
            'type': 'CollectionPage',
            'next': '%s?only_other_accounts=true&page=true' % id_slug,
            'partOf': id_slug,
            'items': [r.to_activity() for r in replies],
        }
    }


def get_replies_page(status, replies):
    ''' actual reply list content '''
    id_slug = status.remote_id + '/replies?page=true&only_other_accounts=true'
    items = []
    for reply in replies:
        if reply.user.local:
            items.append(reply.to_activity())
        else:
            items.append(reply.remote_id)
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': id_slug,
        'type': 'CollectionPage',
        'next': '%s&min_id=%d' % (id_slug, replies[len(replies) - 1].id),
        'partOf': status.remote_id + '/replies',
        'items': [items]
    }


def get_favorite(favorite):
    ''' like a post '''
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': favorite.remote_id,
        'type': 'Like',
        'actor': favorite.user.remote_id,
        'object': favorite.status.remote_id,
    }


def get_unfavorite(favorite):
    ''' like a post '''
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': '%s/undo' % favorite.remote_id,
        'type': 'Undo',
        'actor': favorite.user.remote_id,
        'object': {
            'id': favorite.remote_id,
            'type': 'Like',
            'actor': favorite.user.remote_id,
            'object': favorite.status.remote_id,
        }
    }


def get_add_tag(tag):
    ''' add activity for tagging a book '''
    uuid = uuid4()
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': str(uuid),
        'type': 'Add',
        'actor': tag.user.remote_id,
        'object': {
            'type': 'Tag',
            'id': tag.remote_id,
            'name': tag.name,
        },
        'target': {
            'type': 'Book',
            'id': tag.book.local_id,
        }
    }


def get_remove_tag(tag):
    ''' add activity for tagging a book '''
    uuid = uuid4()
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': str(uuid),
        'type': 'Remove',
        'actor': tag.user.remote_id,
        'object': {
            'type': 'Tag',
            'id': tag.remote_id,
            'name': tag.name,
        },
        'target': {
            'type': 'Book',
            'id': tag.book.local_id,
        }
    }
