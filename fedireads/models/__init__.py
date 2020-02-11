''' bring all the models into the app namespace '''
from .book import Shelf, ShelfBook, Book, Author
from .user import User, FederatedServer
from .activity import Activity, ShelveActivity, FollowActivity, Review, Note

