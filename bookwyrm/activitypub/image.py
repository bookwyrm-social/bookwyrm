""" an image, nothing fancy """
from dataclasses import dataclass
from .base_activity import ActivityObject


@dataclass(init=False)
class Document(ActivityObject):
    """a document"""

    url: str
    name: str = ""
    type: str = "Document"
    id: str = None


@dataclass(init=False)
class Image(Document):
    """an image"""

    type: str = "Image"
