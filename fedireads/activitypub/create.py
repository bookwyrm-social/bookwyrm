''' format Create activities and sign them '''
from base64 import b64encode
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256

def get_create(user, status_json):
    ''' create activitypub json for a Create activity '''
    signer = pkcs1_15.new(RSA.import_key(user.private_key))
    content = status_json['content']
    signed_message = signer.sign(SHA256.new(content.encode('utf8')))
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',

        'id': '%s/activity' % status_json['id'],
        'type': 'Create',
        'actor': user.remote_id,
        'published': status_json['published'],

        'to': ['%s/followers' % user.remote_id],
        'cc': ['https://www.w3.org/ns/activitystreams#Public'],

        'object': status_json,
        'signature': {
            'type': 'RsaSignature2017',
            'creator': '%s#main-key' % user.remote_id,
            'created': status_json['published'],
            'signatureValue': b64encode(signed_message).decode('utf8'),
        }
    }


def get_update(user, activity_json):
    ''' a user profile or book or whatever got updated '''
    # TODO: should this have a signature??
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': 'https://friend.camp/users/tripofmice#updates/1585446332',
        'type': 'Update',
        'actor': user.remote_id,
        'to': [
            'https://www.w3.org/ns/activitystreams#Public'
        ],

        'object': activity_json,
    }
