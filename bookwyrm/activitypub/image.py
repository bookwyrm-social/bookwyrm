''' an image, nothing fancy '''
from dataclasses import dataclass

@dataclass
class Image:
    ''' image block '''
    url: str
    name: str = ''
    type: str = 'Image'
