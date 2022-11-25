""" functionality outline for a book data connector """
from abc import ABC, abstractmethod
import imghdr
import logging
import re

from django.core.files.base import ContentFile
from django.db import transaction
import requests
from requests.exceptions import RequestException

from bookwyrm import activitypub, models, settings
from .connector_manager import load_more_data, ConnectorException, raise_not_valid_url
from .format_mappings import format_mappings


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
        ]
        for field in self_fields:
            setattr(self, field, getattr(info, field))

    def get_search_url(self, query):
        """format the query url"""
        # Check if the query resembles an ISBN
        if maybe_isbn(query) and self.isbn_search_url and self.isbn_search_url != "":
            # Up-case the ISBN string to ensure any 'X' check-digit is correct
            # If the ISBN has only 9 characters, prepend missing zero
            normalized_query = query.strip().upper().rjust(10, "0")
            return f"{self.isbn_search_url}{normalized_query}"
        # NOTE: previously, we tried searching isbn and if that produces no results,
        # searched as free text. This, instead, only searches isbn if it's isbn-y
        return f"{self.search_url}{query}"

    def process_search_response(self, query, data, min_confidence):
        """Format the search results based on the formt of the query"""
        if maybe_isbn(query):
            return list(self.parse_isbn_search_data(data))[:10]
        return list(self.parse_search_data(data, min_confidence))[:10]

    @abstractmethod
    def get_or_create_book(self, remote_id):
        """pull up a book record by whatever means possible"""

    @abstractmethod
    def parse_search_data(self, data, min_confidence):
        """turn the result json from a search into a list"""

    @abstractmethod
    def parse_isbn_search_data(self, data):
        """turn the result json from a search into a list"""


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

        # load the json data from the remote data source
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
            except (KeyError, ConnectorException) as err:
                logger.info(err)
                work_data = data

        if not work_data or not edition_data:
            raise ConnectorException(f"Unable to load book data: {remote_id}")

        with transaction.atomic():
            # create activitypub object
            work_activity = activitypub.Work(
                **dict_from_mappings(work_data, self.book_mappings)
            )
            # this will dedupe automatically
            work = work_activity.to_model(model=models.Work, overwrite=False)
            for author in self.get_authors_from_data(work_data):
                work.authors.add(author)

            edition = self.create_edition_from_data(work, edition_data)
        load_more_data.delay(self.connector.id, work.id)
        return edition

    def get_book_data(self, remote_id):  # pylint: disable=no-self-use
        """this allows connectors to override the default behavior"""
        return get_data(remote_id)

    def create_edition_from_data(self, work, edition_data, instance=None):
        """if we already have the work, we're ready"""
        mapped_data = dict_from_mappings(edition_data, self.book_mappings)
        mapped_data["work"] = work.remote_id
        edition_activity = activitypub.Edition(**mapped_data)
        edition = edition_activity.to_model(
            model=models.Edition, overwrite=False, instance=instance
        )

        # if we're updating an existing instance, we don't need to load authors
        if instance:
            return edition

        if not edition.connector:
            edition.connector = self.connector
            edition.save(broadcast=False, update_fields=["connector"])

        for author in self.get_authors_from_data(edition_data):
            edition.authors.add(author)
        # use the authors from the work if none are found for the edition
        if not edition.authors.exists() and work.authors.exists():
            edition.authors.set(work.authors.all())

        return edition

    def get_or_create_author(self, remote_id, instance=None):
        """load that author"""
        if not instance:
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
        return activity.to_model(
            model=models.Author, overwrite=False, instance=instance
        )

    def get_remote_id_from_model(self, obj):
        """given the data stored, how can we look this up"""
        return getattr(obj, getattr(self, "generated_remote_link_field"))

    def update_author_from_remote(self, obj):
        """load the remote data from this connector and add it to an existing author"""
        remote_id = self.get_remote_id_from_model(obj)
        return self.get_or_create_author(remote_id, instance=obj)

    def update_book_from_remote(self, obj):
        """load the remote data from this connector and add it to an existing book"""
        remote_id = self.get_remote_id_from_model(obj)
        data = self.get_book_data(remote_id)
        return self.create_edition_from_data(obj.parent_work, data, instance=obj)

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


def get_data(url, params=None, timeout=settings.QUERY_TIMEOUT):
    """wrapper for request.get"""
    # check if the url is blocked
    raise_not_valid_url(url)

    try:
        resp = requests.get(
            url,
            params=params,
            headers={  # pylint: disable=line-too-long
                "Accept": (
                    'application/json, application/activity+json, application/ld+json; profile="https://www.w3.org/ns/activitystreams"; charset=utf-8'
                ),
                "User-Agent": settings.USER_AGENT,
            },
            timeout=timeout,
        )
    except RequestException as err:
        logger.info(err)
        raise ConnectorException(err)

    if not resp.ok:
        raise ConnectorException()
    try:
        data = resp.json()
    except ValueError as err:
        logger.info(err)
        raise ConnectorException(err)

    return data


def get_image(url, timeout=10):
    """wrapper for requesting an image"""
    raise_not_valid_url(url)
    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": settings.USER_AGENT,
            },
            timeout=timeout,
        )
    except RequestException as err:
        logger.info(err)
        return None, None

    if not resp.ok:
        return None, None

    image_content = ContentFile(resp.content)
    extension = imghdr.what(None, image_content.read())
    if not extension:
        logger.info("File requested was not an image: %s", url)
        return None, None

    return image_content, extension


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


def infer_physical_format(format_text):
    """try to figure out what the standardized format is from the free value"""
    format_text = format_text.lower()
    if format_text in format_mappings:
        # try a direct match
        return format_mappings[format_text]
    # failing that, try substring
    matches = [v for k, v in format_mappings.items() if k in format_text]
    if not matches:
        return None
    return matches[0]


def unique_physical_format(format_text):
    """only store the format if it isn't diretly in the format mappings"""
    format_text = format_text.lower()
    if format_text in format_mappings:
        # try a direct match, so saving this would be redundant
        return None
    return format_text


def maybe_isbn(query):
    """check if a query looks like an isbn"""
    isbn = re.sub(r"[\W_]", "", query)  # removes filler characters
    # ISBNs must be numeric except an ISBN10 checkdigit can be 'X'
    if not isbn.upper().rstrip("X").isnumeric():
        return False
    return len(isbn) in [
        9,
        10,
        13,
    ]  # ISBN10 or ISBN13, or maybe ISBN10 missing a leading zero
