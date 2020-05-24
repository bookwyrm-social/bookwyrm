''' basics for an activitypub serializer '''
from dataclasses import dataclass, fields, MISSING
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
        ''' treat fields as required but not exhaustive '''
        for field in fields(self):
            try:
                value = kwargs[field.name]
            except KeyError:
                if field.default == MISSING:
                    raise TypeError('Missing required field: %s' % field.name)
                value = field.default
            setattr(self, field.name, value)


    def serialize(self):
        data = self.__dict__
        data['@context'] = 'https://www.w3.org/ns/activitystreams'
        return data
