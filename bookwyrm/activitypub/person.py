''' actor serializer '''
from dataclasses import dataclass, field
from typing import Dict

from .base_activity import ActivityObject
from .image import Image


@dataclass(init=False)
class PublicKey(ActivityObject):
    ''' public key block '''
    owner: str
    publicKeyPem: str
    type: str = 'PublicKey'


@dataclass(init=False)
class Person(ActivityObject):
    ''' actor activitypub json '''
    preferredUsername: str
    name: str
    inbox: str
    outbox: str
    followers: str
    summary: str
    publicKey: PublicKey
    endpoints: Dict
    icon: Image = field(default_factory=lambda: {})
    bookwyrmUser: bool = False
    manuallyApprovesFollowers: str = False
    discoverable: str = True
    type: str = 'Person'
