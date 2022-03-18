""" interface with whatever connectors the app has """
from datetime import datetime
import importlib
import logging
import re
from urllib.parse import urlparse

from django.dispatch import receiver
from django.db.models import signals

from requests import HTTPError

from bookwyrm import book_search, models
from bookwyrm.settings import SEARCH_TIMEOUT
from bookwyrm.tasks import app

logger = logging.getLogger(__name__)


class ConnectorException(HTTPError):
    """when the connector can't do what was asked"""


def search(query, min_confidence=0.1, return_first=False):
    """find books based on arbitary keywords"""
    if not query:
        return []
    results = []

    # Have we got a ISBN ?
    isbn = re.sub(r"[\W_]", "", query)
    maybe_isbn = len(isbn) in [10, 13]  # ISBN10 or ISBN13

    start_time = datetime.now()
    for connector in get_connectors():
        result_set = None
        if maybe_isbn and connector.isbn_search_url and connector.isbn_search_url != "":
            # Search on ISBN
            try:
                result_set = connector.isbn_search(isbn)
            except Exception as err:  # pylint: disable=broad-except
                logger.info(err)
                # if this fails, we can still try regular search

        # if no isbn search results, we fallback to generic search
        if not result_set:
            try:
                result_set = connector.search(query, min_confidence=min_confidence)
            except Exception as err:  # pylint: disable=broad-except
                # we don't want *any* error to crash the whole search page
                logger.info(err)
                continue

        if return_first and result_set:
            # if we found anything, return it
            return result_set[0]

        if result_set:
            results.append(
                {
                    "connector": connector,
                    "results": result_set,
                }
            )
        if (datetime.now() - start_time).seconds >= SEARCH_TIMEOUT:
            break

    if return_first:
        return None

    return results


def first_search_result(query, min_confidence=0.1):
    """search until you find a result that fits"""
    # try local search first
    result = book_search.search(query, min_confidence=min_confidence, return_first=True)
    if result:
        return result
    # otherwise, try remote endpoints
    return search(query, min_confidence=min_confidence, return_first=True) or None


def get_connectors():
    """load all connectors"""
    for info in models.Connector.objects.filter(active=True).order_by("priority").all():
        yield load_connector(info)


def get_or_create_connector(remote_id):
    """get the connector related to the object's server"""
    url = urlparse(remote_id)
    identifier = url.netloc
    if not identifier:
        raise ValueError("Invalid remote id")

    try:
        connector_info = models.Connector.objects.get(identifier=identifier)
    except models.Connector.DoesNotExist:
        connector_info = models.Connector.objects.create(
            identifier=identifier,
            connector_file="bookwyrm_connector",
            base_url=f"https://{identifier}",
            books_url=f"https://{identifier}/book",
            covers_url=f"https://{identifier}/images/covers",
            search_url=f"https://{identifier}/search?q=",
            priority=2,
        )

    return load_connector(connector_info)


@app.task(queue="low_priority")
def load_more_data(connector_id, book_id):
    """background the work of getting all 10,000 editions of LoTR"""
    connector_info = models.Connector.objects.get(id=connector_id)
    connector = load_connector(connector_info)
    book = models.Book.objects.select_subclasses().get(id=book_id)
    connector.expand_book_data(book)


def load_connector(connector_info):
    """instantiate the connector class"""
    connector = importlib.import_module(
        f"bookwyrm.connectors.{connector_info.connector_file}"
    )
    return connector.Connector(connector_info.identifier)


@receiver(signals.post_save, sender="bookwyrm.FederatedServer")
# pylint: disable=unused-argument
def create_connector(sender, instance, created, *args, **kwargs):
    """create a connector to an external bookwyrm server"""
    if instance.application_type == "bookwyrm":
        get_or_create_connector(f"https://{instance.server_name}")
