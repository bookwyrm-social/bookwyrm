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
    signature: Signature = None
    type: str = 'Create'

    def action(self):
        ''' create the model instance from the dataclass '''
        # check for dupes
        self.object.to_model()


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
    object: str
    type: str = 'Follow'

@dataclass(init=False)
class Block(Verb):
    ''' Block activity '''
    object: str
    type: str = 'Block'

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
    target: str
    object: ActivityObject
    type: str = 'Add'


@dataclass(init=False)
class AddBook(Add):
    '''Add activity that's aware of the book obj '''
    object: Edition
    type: str = 'Add'


@dataclass(init=False)
class AddListItem(AddBook):
    '''Add activity that's aware of the book obj '''
    notes: str = None
    order: int = 0
    approved: bool = True


@dataclass(init=False)
class Remove(Verb):
    '''Remove activity '''
    target: ActivityObject
    type: str = 'Remove'
