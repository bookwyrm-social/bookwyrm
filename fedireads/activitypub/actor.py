''' actor serializer '''

def get_actor(user):
    ''' activitypub actor from db User '''
    return {
        '@context': [
            'https://www.w3.org/ns/activitystreams',
            'https://w3id.org/security/v1'
        ],

        'id': user.actor,
        'type': 'Person',
        'preferredUsername': user.localname,
        'name': user.name,
        'inbox': user.inbox,
        'outbox': '%s/outbox' % user.actor,
        'followers': '%s/followers' % user.actor,
        'following': '%s/following' % user.actor,
        'summary': user.summary,
        'publicKey': {
            'id': '%s/#main-key' % user.actor,
            'owner': user.actor,
            'publicKeyPem': user.public_key,
        },
        'endpoints': {
            'sharedInbox': user.shared_inbox,
        },
        'fedireadsUser': True,
    }

