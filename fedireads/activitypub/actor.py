''' actor serializer '''
from dataclasses import dataclass
from typing import Dict

@dataclass
class Image:
    mediaType: str
    url: str
    type: str = 'Image'


@dataclass
class User:
    ''' actor activitypub json '''
    id: str
    type: str
    preferredUsername: str
    inbox: str
    outbox: str
    followers: str
    summary: str
    publicKey: Dict
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
