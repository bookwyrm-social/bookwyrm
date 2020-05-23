''' actor serializer '''
from dataclasses import dataclass
from typing import Dict

from .base_activity import ActivityObject, Image, PublicKey

@dataclass
class User(ActivityObject):
    ''' actor activitypub json '''
    preferredUsername: str
    name: str
    inbox: str
    outbox: str
    followers: str
    summary: str
    publicKey: PublicKey
    endpoints: Dict
    icon: Image
    fedireadsUser: str = False
    manuallyApprovesFollowers: str = False
    discoverable: str = True

    def serialize(self):
        data = self.__dict__
        data['@context'] = [
            'https://www.w3.org/ns/activitystreams',
            'https://w3id.org/security/v1',
            {
                'manuallyApprovesFollowers': 'as:manuallyApprovesFollowers',
                'schema': 'http://schema.org#',
                'PropertyValue': 'schema:PropertyValue',
                'value': 'schema:value',
            }
        ]
        return data
