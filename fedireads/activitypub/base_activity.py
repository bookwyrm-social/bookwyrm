''' basics for an activitypub serializer '''
import dataclasses
from dataclasses import dataclass
from json import JSONEncoder
from typing import Dict


class ActivityEncoder(JSONEncoder):
    def default(self, o):
        return o.__dict__


@dataclass
class Image:
    mediaType: str
    url: str
    type: str = 'Image'


@dataclass
class PublicKey:
    id: str
    owner: str
    publicKeyPem: str


@dataclass(init=False)
class ActivityObject:
    ''' actor activitypub json '''
    id: str
    type: str

    def __init__(self, **kwargs):
        ''' silently ignore unexpected fields '''
        names = set([f.name for f in dataclasses.fields(self)])
        for k, v in kwargs.items():
            if k in names:
                setattr(self, k, v)

    def serialize(self):
        data = self.__dict__
        data['@context'] = 'https://www.w3.org/ns/activitystreams'
        return data
