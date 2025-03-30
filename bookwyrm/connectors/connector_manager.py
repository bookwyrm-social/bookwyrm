""" interface with whatever connectors the app has """
from __future__ import annotations
import asyncio
import importlib
import ipaddress
import logging
from asyncio import Future
from typing import Iterator, Any, Optional, Union, overload, Literal
from urllib.parse import urlparse

import aiohttp
from django.dispatch import receiver
from django.db.models import signals

from requests import HTTPError

from bookwyrm import book_search, models
from bookwyrm.book_search import SearchResult
from bookwyrm.connectors import abstract_connector
from bookwyrm.settings import SEARCH_TIMEOUT
from bookwyrm.tasks import app, CONNECTORS

logger = logging.getLogger(__name__)


class ConnectorException(HTTPError):
    """when the connector can't do what was asked"""


async def async_connector_search(
    query: str,
    items: list[tuple[str, abstract_connector.AbstractConnector]],
    min_confidence: float,
) -> list[Optional[abstract_connector.ConnectorResults]]:
    """Try a number of requests simultaneously"""
    timeout = aiohttp.ClientTimeout(total=SEARCH_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        tasks: list[Future[Optional[abstract_connector.ConnectorResults]]] = []
        for url, connector in items:
            tasks.append(
                asyncio.ensure_future(
                    connector.get_results(session, url, min_confidence, query)
                )
            )

        results = await asyncio.gather(*tasks)
        return list(results)


@overload
def search(
    query: str, *, min_confidence: float = 0.1, return_first: Literal[False]
) -> list[abstract_connector.ConnectorResults]:
    ...


@overload
def search(
    query: str, *, min_confidence: float = 0.1, return_first: Literal[True]
) -> Optional[SearchResult]:
    ...


def search(
    query: str, *, min_confidence: float = 0.1, return_first: bool = False
) -> Union[list[abstract_connector.ConnectorResults], Optional[SearchResult]]:
    """find books based on arbitrary keywords"""
    if not query:
        return None if return_first else []

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
    # failed requests will return None, so filter those out
    results = [
        r
        for r in asyncio.run(async_connector_search(query, items, min_confidence))
        if r
    ]

    if return_first:
        # find the best result from all the responses and return that
        all_results = [r for con in results for r in con["results"]]
        all_results = sorted(all_results, key=lambda r: r.confidence, reverse=True)
        return all_results[0] if all_results else None

    return results


def first_search_result(
    query: str, min_confidence: float = 0.1
) -> Union[models.Edition, SearchResult, None]:
    """search until you find a result that fits"""
    # try local search first
    result = book_search.search(query, min_confidence=min_confidence, return_first=True)
    if result:
        return result
    # otherwise, try remote endpoints
    return search(query, min_confidence=min_confidence, return_first=True) or None


def get_connectors() -> Iterator[abstract_connector.AbstractConnector]:
    """load all connectors"""
    for info in models.Connector.objects.filter(active=True).order_by("priority").all():
        yield load_connector(info)


def get_or_create_connector(remote_id: str) -> abstract_connector.AbstractConnector:
    """get the connector related to the object's server"""
    url = urlparse(remote_id)
    identifier = url.hostname
    if not identifier:
        raise ValueError(f"Invalid remote id: {remote_id}")

    base_url = f"{url.scheme}://{url.netloc}"

    try:
        connector_info = models.Connector.objects.get(identifier=identifier)
    except models.Connector.DoesNotExist:
        connector_info = models.Connector.objects.create(
            identifier=identifier,
            connector_file="bookwyrm_connector",
            base_url=base_url,
            books_url=f"{base_url}/book",
            covers_url=f"{base_url}/images/covers",
            search_url=f"{base_url}/search?q=",
            priority=2,
        )

    return load_connector(connector_info)


@app.task(queue=CONNECTORS)
def load_more_data(connector_id: str, book_id: str) -> None:
    """background the work of getting all 10,000 editions of LoTR"""
    connector_info = models.Connector.objects.get(id=connector_id)
    connector = load_connector(connector_info)
    book = models.Book.objects.select_subclasses().get(  # type: ignore[no-untyped-call]
        id=book_id
    )
    connector.expand_book_data(book)


@app.task(queue=CONNECTORS)
def create_edition_task(
    connector_id: int, work_id: int, data: Union[str, abstract_connector.JsonDict]
) -> None:
    """separate task for each of the 10,000 editions of LoTR"""
    connector_info = models.Connector.objects.get(id=connector_id)
    connector = load_connector(connector_info)
    work = models.Work.objects.select_subclasses().get(  # type: ignore[no-untyped-call]
        id=work_id
    )
    connector.create_edition_from_data(work, data)


def load_connector(
    connector_info: models.Connector,
) -> abstract_connector.AbstractConnector:
    """instantiate the connector class"""
    connector = importlib.import_module(
        f"bookwyrm.connectors.{connector_info.connector_file}"
    )
    return connector.Connector(connector_info.identifier)  # type: ignore[no-any-return]


@receiver(signals.post_save, sender="bookwyrm.FederatedServer")
# pylint: disable=unused-argument
def create_connector(
    sender: Any,
    instance: models.FederatedServer,
    created: Any,
    *args: Any,
    **kwargs: Any,
) -> None:
    """create a connector to an external bookwyrm server"""
    if instance.application_type == "bookwyrm":
        get_or_create_connector(f"https://{instance.server_name}")


def raise_not_valid_url(url: str) -> None:
    """do some basic reality checks on the url"""
    parsed = urlparse(url)
    if not parsed.scheme in ["http", "https"]:
        raise ConnectorException("Invalid scheme: ", url)

    if not parsed.hostname:
        raise ConnectorException("Hostname missing: ", url)

    try:
        ipaddress.ip_address(parsed.hostname)
        raise ConnectorException("Provided url is an IP address: ", url)
    except ValueError:
        # it's not an IP address, which is good
        pass

    if models.FederatedServer.is_blocked(url):
        raise ConnectorException(f"Attempting to load data from blocked url: {url}")


def create_finna_connector() -> None:
    """create a Finna connector"""

    models.Connector.objects.create(
        identifier="api.finna.fi",
        name="Finna API",
        connector_file="finna",
        base_url="https://www.finna.fi",
        books_url="https://api.finna.fi/api/v1/record" "?id=",
        covers_url="https://api.finna.fi",
        search_url="https://api.finna.fi/api/v1/search?limit=20"
        "&filter[]=format%3a%220%2fBook%2f%22"
        "&field[]=title&field[]=recordPage&field[]=authors"
        "&field[]=year&field[]=id&field[]=formats&field[]=images"
        "&lookfor=",
        isbn_search_url="https://api.finna.fi/api/v1/search?limit=1"
        "&filter[]=format%3a%220%2fBook%2f%22"
        "&field[]=title&field[]=recordPage&field[]=authors&field[]=year"
        "&field[]=id&field[]=formats&field[]=images"
        "&lookfor=isbn:",
    )
