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


def get_accept(user, to_follow, request_activity):
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': '%s#accepts/follows/' % to_follow.absolute_id,
        'type': 'Accept',
        'actor': to_follow.actor,
        'object': activity,
    }

