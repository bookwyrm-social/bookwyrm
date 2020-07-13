''' activitypub json for collections '''
from dataclasses import dataclass

from .base_activity import ActivityObject, OrderedCollectionPage


@dataclass(init=False)
class Outbox(ActivityObject):
    ''' entrypoint to the list of user statuses '''
    id: str
    totalItems: int
    first: str
    last: str
    type: str = 'OrderedCollection'


class OutboxPage(OrderedCollectionPage):
    ''' actual list of user statuses '''
