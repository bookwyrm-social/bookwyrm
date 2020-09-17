''' boosting and liking posts '''
from dataclasses import dataclass

from .base_activity import ActivityObject


@dataclass(init=False)
class Like(ActivityObject):
    ''' a user faving an object '''
    actor: str
    object: str
    type: str = 'Like'


@dataclass(init=False)
class Boost(ActivityObject):
    ''' boosting a status '''
    actor: str
    object: str
    type: str = 'Announce'
