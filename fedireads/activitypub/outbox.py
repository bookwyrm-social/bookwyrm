''' activitypub json for collections '''
from dataclasses import dataclass

from .base_activity import OrderedCollection


@dataclass(init=False)
class Outbox(OrderedCollection):
    ''' entrypoint to the list of user statuses '''
    last: str
