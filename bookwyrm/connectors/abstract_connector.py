""" functionality outline for a book data connector """
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
import logging
from urllib3.exceptions import RequestError

from django.db import transaction
import requests
from requests.exceptions import SSLError

from bookwyrm import activitypub, models, settings
from .connector_manager import load_more_data, ConnectorException


logger = logging.getLogger(__name__)


class AbstractMinimalConnector(ABC):
    """just the bare bones, for other bookwyrm instances"""

    def __init__(self, identifier):
        # load connector settings
        info = models.Connector.objects.get(identifier=identifier)
        self.connector = info

        # the things in the connector model to copy over
        self_fields = [
            "base_url",
            "books_url",
            "covers_url",
            "search_url",
            "isbn_search_url",
            "name",
            "identifier",
            "local",
        ]
        for field in self_fields:
            setattr(self, field, getattr(info, field))

    def search(self, query, min_confidence=None, timeout=5):
        """free text search"""
        params = {}
        if min_confidence:
            params["min_confidence"] = min_confidence

        data = self.get_search_data(
            "%s%s" % (self.search_url, query),
            params=params,
            timeout=timeout,
        )
        results = []

        for doc in self.parse_search_data(data)[:10]:
            results.append(self.format_search_result(doc))
        return results

    def isbn_search(self, query):
        """isbn search"""
        params = {}
        data = self.get_search_data(
            "%s%s" % (self.isbn_search_url, query),
            params=params,
        )
        results = []

        # this shouldn't be returning mutliple results, but just in case
        for doc in self.parse_isbn_search_data(data)[:10]:
            results.append(self.format_isbn_search_result(doc))
        return results

    def get_search_data(self, remote_id, **kwargs):  # pylint: disable=no-self-use
        """this allows connectors to override the default behavior"""
        return get_data(remote_id, **kwargs)

    @abstractmethod
    def get_or_create_book(self, remote_id):
        """pull up a book record by whatever means possible"""

    @abstractmethod
    def parse_search_data(self, data):
        """turn the result json from a search into a list"""

    @abstractmethod
    def format_search_result(self, search_result):
        """create a SearchResult obj from json"""

    @abstractmethod
    def parse_isbn_search_data(self, data):
        """turn the result json from a search into a list"""

    @abstractmethod
    def format_isbn_search_result(self, search_result):
        """create a SearchResult obj from json"""


class AbstractConnector(AbstractMinimalConnector):
    """generic book data connector"""

    def __init__(self, identifier):
        super().__init__(identifier)
        # fields we want to look for in book data to copy over
        # title we handle separately.
        self.book_mappings = []

    def get_or_create_book(self, remote_id):
        """translate arbitrary json into an Activitypub dataclass"""
        # first, check if we have the origin_id saved
        existing = models.Edition.find_existing_by_remote_id(
            remote_id
        ) or models.Work.find_existing_by_remote_id(remote_id)
        if existing:
            if hasattr(existing, "default_edition"):
                return existing.default_edition
            return existing

        # load the json
        data = self.get_book_data(remote_id)
        if self.is_work_data(data):
            try:
                edition_data = self.get_edition_from_work_data(data)
            except (KeyError, ConnectorException):
                # hack: re-use the work data as the edition data
                # this is why remote ids aren't necessarily unique
                edition_data = data
            work_data = data
        else:
            edition_data = data
            try:
                work_data = self.get_work_from_edition_data(data)
            except (KeyError, ConnectorException) as e:
                logger.exception(e)
                work_data = data

        if not work_data or not edition_data:
            raise ConnectorException("Unable to load book data: %s" % remote_id)

        with transaction.atomic():
            # create activitypub object
            work_activity = activitypub.Work(
                **dict_from_mappings(work_data, self.book_mappings)
            )
            # this will dedupe automatically
            work = work_activity.to_model(model=models.Work)
            for author in self.get_authors_from_data(work_data):
                work.authors.add(author)

            edition = self.create_edition_from_data(work, edition_data)
        load_more_data.delay(self.connector.id, work.id)
        return edition

    def get_book_data(self, remote_id):  # pylint: disable=no-self-use
        """this allows connectors to override the default behavior"""
        return get_data(remote_id)

    def create_edition_from_data(self, work, edition_data):
        """if we already have the work, we're ready"""
        mapped_data = dict_from_mappings(edition_data, self.book_mappings)
        mapped_data["work"] = work.remote_id
        edition_activity = activitypub.Edition(**mapped_data)
        edition = edition_activity.to_model(model=models.Edition)
        edition.connector = self.connector
        edition.save()

        for author in self.get_authors_from_data(edition_data):
            edition.authors.add(author)
        if not edition.authors.exists() and work.authors.exists():
            edition.authors.set(work.authors.all())

        return edition

    def get_or_create_author(self, remote_id):
        """load that author"""
        existing = models.Author.find_existing_by_remote_id(remote_id)
        if existing:
            return existing

        data = self.get_book_data(remote_id)

        mapped_data = dict_from_mappings(data, self.author_mappings)
        try:
            activity = activitypub.Author(**mapped_data)
        except activitypub.ActivitySerializerError:
            return None

        # this will dedupe
        return activity.to_model(model=models.Author)

    @abstractmethod
    def is_work_data(self, data):
        """differentiate works and editions"""

    @abstractmethod
    def get_edition_from_work_data(self, data):
        """every work needs at least one edition"""

    @abstractmethod
    def get_work_from_edition_data(self, data):
        """every edition needs a work"""

    @abstractmethod
    def get_authors_from_data(self, data):
        """load author data"""

    @abstractmethod
    def expand_book_data(self, book):
        """get more info on a book"""


def dict_from_mappings(data, mappings):
    """create a dict in Activitypub format, using mappings supplies by
    the subclass"""
    result = {}
    for mapping in mappings:
        # sometimes there are multiple mappings for one field, don't
        # overwrite earlier writes in that case
        if mapping.local_field in result and result[mapping.local_field]:
            continue
        result[mapping.local_field] = mapping.get_value(data)
    return result


def get_data(url, params=None, timeout=10):
    """wrapper for request.get"""
    # check if the url is blocked
    if models.FederatedServer.is_blocked(url):
        raise ConnectorException(
            "Attempting to load data from blocked url: {:s}".format(url)
        )

    try:
        resp = requests.get(
            url,
            params=params,
            headers={
                "Accept": "application/json; charset=utf-8",
                "User-Agent": settings.USER_AGENT,
            },
            timeout=timeout,
        )
    except (RequestError, SSLError, ConnectionError) as e:
        logger.exception(e)
        raise ConnectorException()

    if not resp.ok:
        raise ConnectorException()
    try:
        data = resp.json()
    except ValueError as e:
        logger.exception(e)
        raise ConnectorException()

    return data


def get_image(url, timeout=10):
    """wrapper for requesting an image"""
    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": settings.USER_AGENT,
            },
            timeout=timeout,
        )
    except (RequestError, SSLError) as e:
        logger.exception(e)
        return None
    if not resp.ok:
        return None
    return resp


@dataclass
class SearchResult:
    """standardized search result object"""

    title: str
    key: str
    connector: object
    view_link: str = None
    author: str = None
    year: str = None
    cover: str = None
    confidence: int = 1

    def __repr__(self):
        return "<SearchResult key={!r} title={!r} author={!r}>".format(
            self.key, self.title, self.author
        )

    def json(self):
        """serialize a connector for json response"""
        serialized = asdict(self)
        del serialized["connector"]
        return serialized


class Mapping:
    """associate a local database field with a field in an external dataset"""

    def __init__(self, local_field, remote_field=None, formatter=None):
        noop = lambda x: x

        self.local_field = local_field
        self.remote_field = remote_field or local_field
        self.formatter = formatter or noop

    def get_value(self, data):
        """pull a field from incoming json and return the formatted version"""
        value = data.get(self.remote_field)
        if not value:
            return None
        try:
            return self.formatter(value)
        except:  # pylint: disable=bare-except
            return None
