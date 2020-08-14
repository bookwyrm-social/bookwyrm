''' activitypub json for collections '''
from dataclasses import dataclass

from .base_activity import OrderedCollection, OrderedCollectionPage


@dataclass(init=False)
class Outbox(OrderedCollection):
    ''' entrypoint to the list of user statuses '''
    last: str


class OutboxPage(OrderedCollectionPage):
    ''' actual list of user statuses '''
