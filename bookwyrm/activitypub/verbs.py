''' undo wrapper activity '''
from dataclasses import dataclass
from typing import List

from .base_activity import ActivityObject, Signature
from .book import Edition

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
class Delete(Verb):
    ''' Create activity '''
    to: List
    cc: List
    type: str = 'Delete'


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
    type: str = 'Follow'


@dataclass(init=False)
class Accept(Verb):
    ''' Accept activity '''
    object: Follow
    type: str = 'Accept'


@dataclass(init=False)
class Reject(Verb):
    ''' Reject activity '''
    object: Follow
    type: str = 'Reject'


@dataclass(init=False)
class Add(Verb):
    '''Add activity '''
    target: ActivityObject
    type: str = 'Add'


@dataclass(init=False)
class AddBook(Verb):
    '''Add activity that's aware of the book obj '''
    target: Edition
    type: str = 'Add'


@dataclass(init=False)
class Remove(Verb):
    '''Remove activity '''
    target: ActivityObject
    type: str = 'Remove'
