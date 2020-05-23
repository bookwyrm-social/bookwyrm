''' basics for an activitypub serializer '''
from dataclasses import dataclass
from typing import Dict

@dataclass
class Image:
    mediaType: str
    url: str
    type: str = 'Image'


@dataclass
class ActivityObject:
    ''' actor activitypub json '''
    id: str
    type: str

    def serialize(self):
        data = self.__dict__
        data['@context'] = 'https://www.w3.org/ns/activitystreams'
        return data

