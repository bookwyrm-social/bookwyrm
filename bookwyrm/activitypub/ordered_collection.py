''' defines activitypub collections (lists) '''
from dataclasses import dataclass
from typing import List

from .base_activity import ActivityObject


@dataclass(init=False)
class OrderedCollection(ActivityObject):
    ''' structure of an ordered collection activity '''
    totalItems: int
    first: str
    last: str = ''
    name: str = ''
    owner: str = ''
    type: str = 'OrderedCollection'


@dataclass(init=False)
class OrderedCollectionPage(ActivityObject):
    ''' structure of an ordered collection activity '''
    partOf: str
    orderedItems: List
    next: str
    prev: str
    type: str = 'OrderedCollectionPage'
