''' bring all the models into the app namespace '''
from .book import Shelf, ShelfBook, Book, Author
from .user import User, UserRelationship, FederatedServer
from .status import Status, Review, Favorite, Tag

