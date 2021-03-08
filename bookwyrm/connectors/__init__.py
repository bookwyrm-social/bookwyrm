""" bring connectors into the namespace """
from .settings import CONNECTORS
from .abstract_connector import ConnectorException
from .abstract_connector import get_data, get_image

from .connector_manager import search, local_search, first_search_result
