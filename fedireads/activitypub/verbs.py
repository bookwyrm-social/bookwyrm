''' undo wrapper activity '''
from dataclasses import dataclass
from typing import List

from .base_activity import ActivityObject, Signature

@dataclass(init=False)
class Verb(ActivityObject):
    ''' generic fields for activities - maybe an unecessary level of
        abstraction but w/e '''
    actor: str
    object: ActivityObject


@dataclass(init=False)
class Create(Verb):
    ''' Create activity '''
    to: List
    cc: List
    signature: Signature
    type: str = 'Create'


@dataclass(init=False)
class Update(Verb):
    ''' Update activity '''
    to: List
    type: str = 'Update'


@dataclass(init=False)
class Undo(Verb):
    ''' Undo an activity '''
    type: str = 'Undo'


@dataclass(init=False)
class Follow(Verb):
    ''' Follow activity '''
    summary: str = ''
    type: str = 'Follow'


@dataclass(init=False)
class Accept(Verb):
    ''' Accept activity '''
    type: str = 'Accept'
    object: Follow


@dataclass(init=False)
class Reject(Verb):
    ''' Reject activity '''
    type: str = 'Reject'
    object: Follow
