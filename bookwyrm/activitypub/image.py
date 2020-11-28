''' an image, nothing fancy '''
from dataclasses import dataclass
from .base_activity import ActivityObject

@dataclass(init=False)
class Image(ActivityObject):
    ''' image block '''
    url: str
    name: str = ''
    type: str = 'Image'
    id: str = ''
