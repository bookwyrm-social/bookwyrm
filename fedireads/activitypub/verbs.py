''' undo wrapper activity '''
from dataclasses import dataclass
from typing import List

from .base_activity import ActivityObject, Signature


@dataclass(init=False)
class Create(ActivityObject):
    ''' Note activity '''
    id: str
    actor: str
    to: List
    cc: List
    object: ActivityObject
    signature: Signature
    type: str = 'Create'


@dataclass(init=False)
class Update(ActivityObject):
    ''' Note activity '''
    id: str
    actor: str
    to: List
    object: ActivityObject
    type: str = 'Update'


@dataclass(init=False)
class Undo(ActivityObject):
    ''' Note activity '''
    id: str
    actor: str
    object: ActivityObject
    type: str = 'Undo'
