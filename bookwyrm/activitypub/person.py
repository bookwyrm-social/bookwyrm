''' actor serializer '''
from dataclasses import dataclass, field
from typing import Dict

from .base_activity import ActivityObject, Image, PublicKey

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
    icon: Image = field(default=lambda: {})
    bookwyrmUser: bool = False
    manuallyApprovesFollowers: str = False
    discoverable: str = True
    type: str = 'Person'
