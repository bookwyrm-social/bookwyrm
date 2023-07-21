""" actor serializer """
from dataclasses import dataclass, field
from typing import Dict, Optional

from .base_activity import ActivityObject
from .image import Image


# pylint: disable=invalid-name
@dataclass(init=False)
class PublicKey(ActivityObject):
    """public key block"""

    owner: str
    publicKeyPem: str
    type: str = "PublicKey"

    def serialize(self, **kwargs):
        """remove fields"""
        omit = ("type", "@context")
        return super().serialize(omit=omit)


# pylint: disable=invalid-name
@dataclass(init=False)
class Person(ActivityObject):
    """actor activitypub json"""

    preferredUsername: str
    inbox: str
    publicKey: PublicKey
    followers: Optional[str] = None
    following: Optional[str] = None
    outbox: Optional[str] = None
    endpoints: Optional[Dict] = None
    name: Optional[str] = None
    summary: Optional[str] = None
    icon: Image = field(default_factory=lambda: {})
    bookwyrmUser: bool = False
    manuallyApprovesFollowers: bool = False
    discoverable: bool = False
    hideFollows: bool = False
    type: str = "Person"
