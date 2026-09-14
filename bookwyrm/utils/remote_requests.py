"""Validate and fetch data from remote services."""

from collections.abc import Callable, Mapping
import ipaddress
import socket
from threading import RLock
from typing import Literal, Optional, cast
from urllib.parse import urljoin, urlsplit

from cachetools import TTLCache
import requests

from bookwyrm.utils.ip_utils import check_ip_routable


MAX_REMOTE_REDIRECTS = 3
REMOTE_URL_CACHE_TTL = 30
REMOTE_URL_CACHE_MAX_SIZE = 1000

_remote_url_cache = cast(
    TTLCache[str, set[str], float],
    TTLCache(
        maxsize=REMOTE_URL_CACHE_MAX_SIZE,
        ttl=REMOTE_URL_CACHE_TTL,
    ),
)
_remote_url_cache_lock = RLock()


class RemoteRequestError(ValueError):
    """The requested remote URL is unsafe or cannot be resolved."""


def get_remote_addresses(hostname: str, port: int) -> set[str]:
    """Resolve a hostname to public addresses, reusing recent lookups."""
    cache_key = f"remote-addresses:{hostname}:{port}"
    with _remote_url_cache_lock:
        cached_addresses = _remote_url_cache.get(cache_key)
    if cached_addresses is not None:
        return cached_addresses

    try:
        addresses = {
            result[4][0]
            for result in socket.getaddrinfo(
                hostname,
                port,
                type=socket.SOCK_STREAM,
            )
        }
    except socket.gaierror as err:
        raise RemoteRequestError("Could not resolve remote hostname") from err

    if not addresses or any(not check_ip_routable(address) for address in addresses):
        raise RemoteRequestError("Remote hostname resolves to a non-public address")

    with _remote_url_cache_lock:
        _remote_url_cache[cache_key] = addresses
    return addresses


def validate_remote_url(url: str) -> None:
    """Allow only hostnames that resolve entirely to public addresses."""
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as err:
        raise RemoteRequestError("Invalid remote URL") from err

    if parsed.scheme not in ("http", "https"):
        raise RemoteRequestError("Remote URL must use HTTP or HTTPS")
    if not hostname:
        raise RemoteRequestError("Remote URL is missing a hostname")
    if parsed.username or parsed.password:
        raise RemoteRequestError("Remote URL must not include credentials")

    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise RemoteRequestError("Remote URL must use a hostname")

    get_remote_addresses(hostname, port or (443 if parsed.scheme == "https" else 80))


def get_remote_response(
    url: str,
    *,
    headers: Mapping[str, str] | Callable[[str], Mapping[str, str]],
    timeout: int,
    params: Optional[dict[str, str]] = None,
    method: Literal["get", "head"] = "get",
    validate_url: Callable[[str], None] = validate_remote_url,
) -> requests.Response:
    """Request a remote URL, validating the initial URL and every redirect."""
    current_url = url
    current_params = params

    for _ in range(MAX_REMOTE_REDIRECTS + 1):
        validate_url(current_url)
        request_headers = headers(current_url) if callable(headers) else headers
        if method == "get":
            response = requests.get(
                current_url,
                headers=request_headers,
                params=current_params,
                timeout=timeout,
                allow_redirects=False,
            )
        else:
            response = requests.head(
                current_url,
                headers=request_headers,
                params=current_params,
                timeout=timeout,
                allow_redirects=False,
            )

        if not response.is_redirect:
            return response

        location = response.headers.get("Location")
        if not location:
            return response

        current_url = urljoin(current_url, location)
        current_params = None

    raise RemoteRequestError("Too many remote redirects")
