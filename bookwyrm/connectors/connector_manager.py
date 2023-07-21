""" interface with whatever connectors the app has """
import asyncio
import importlib
import ipaddress
import logging
from urllib.parse import urlparse

import aiohttp
from django.dispatch import receiver
from django.db.models import signals

from requests import HTTPError

from bookwyrm import book_search, models
from bookwyrm.settings import SEARCH_TIMEOUT
from bookwyrm.tasks import app, CONNECTORS

logger = logging.getLogger(__name__)


class ConnectorException(HTTPError):
    """when the connector can't do what was asked"""


async def async_connector_search(query, items, min_confidence):
    """Try a number of requests simultaneously"""
    timeout = aiohttp.ClientTimeout(total=SEARCH_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        tasks = []
        for url, connector in items:
            tasks.append(
                asyncio.ensure_future(
                    connector.get_results(session, url, min_confidence, query)
                )
            )

        results = await asyncio.gather(*tasks)
        return results


def search(query, min_confidence=0.1, return_first=False):
    """find books based on arbitrary keywords"""
    if not query:
        return []
    results = []

    items = []
    for connector in get_connectors():
        # get the search url from the connector before sending
        url = connector.get_search_url(query)
        try:
            raise_not_valid_url(url)
        except ConnectorException:
            # if this URL is invalid we should skip it and move on
            logger.info("Request denied to blocked domain: %s", url)
            continue
        items.append((url, connector))

    # load as many results as we can
    results = asyncio.run(async_connector_search(query, items, min_confidence))
    results = [r for r in results if r]

    if return_first:
        # find the best result from all the responses and return that
        all_results = [r for con in results for r in con["results"]]
        all_results = sorted(all_results, key=lambda r: r.confidence, reverse=True)
        return all_results[0] if all_results else None

    # failed requests will return None, so filter those out
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


@app.task(queue=CONNECTORS)
def load_more_data(connector_id, book_id):
    """background the work of getting all 10,000 editions of LoTR"""
    connector_info = models.Connector.objects.get(id=connector_id)
    connector = load_connector(connector_info)
    book = models.Book.objects.select_subclasses().get(id=book_id)
    connector.expand_book_data(book)


@app.task(queue=CONNECTORS)
def create_edition_task(connector_id, work_id, data):
    """separate task for each of the 10,000 editions of LoTR"""
    connector_info = models.Connector.objects.get(id=connector_id)
    connector = load_connector(connector_info)
    work = models.Work.objects.select_subclasses().get(id=work_id)
    connector.create_edition_from_data(work, data)


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


def raise_not_valid_url(url):
    """do some basic reality checks on the url"""
    parsed = urlparse(url)
    if not parsed.scheme in ["http", "https"]:
        raise ConnectorException("Invalid scheme: ", url)

    try:
        ipaddress.ip_address(parsed.netloc)
        raise ConnectorException("Provided url is an IP address: ", url)
    except ValueError:
        # it's not an IP address, which is good
        pass

    if models.FederatedServer.is_blocked(url):
        raise ConnectorException(f"Attempting to load data from blocked url: {url}")
