''' activitypub json for collections '''
from urllib.parse import urlencode

from .status import get_status, get_review

def get_outbox(user, size):
    ''' helper function for creating an outbox '''
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': user.outbox,
        'type': 'OrderedCollection',
        'totalItems': size,
        'first': '%s?page=true' % user.outbox,
        'last': '%s?min_id=0&page=true' % user.outbox
    }


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
        if status.status_type == 'Review':
            status_activity = get_review(status)
        else:
            status_activity = get_status(status)
        page['orderedItems'].append(status_activity)

    if max_id:
        page['next'] = user.outbox + '?' + \
            urlencode({'min_id': max_id, 'page': 'true'})
    if min_id:
        page['prev'] = user.outbox + '?' + \
            urlencode({'max_id': min_id, 'page': 'true'})

    return page



