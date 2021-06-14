""" actor serializer """
from dataclasses import dataclass, field
from typing import Dict

from .base_activity import ActivityObject
from .image import Image


@dataclass(init=False)
class PublicKey(ActivityObject):
    """public key block"""

    owner: str
    publicKeyPem: str
    type: str = "PublicKey"


@dataclass(init=False)
class Person(ActivityObject):
    """actor activitypub json"""

    preferredUsername: str
    inbox: str
    publicKey: PublicKey
    followers: str = None
    following: str = None
    outbox: str = None
    endpoints: Dict = None
    name: str = None
    summary: str = None
    icon: Image = field(default_factory=lambda: {})
    bookwyrmUser: bool = False
    manuallyApprovesFollowers: str = False
    discoverable: str = False
    type: str = "Person"
