"""Validate and fetch data from remote services."""

from collections.abc import Callable, Mapping
import ipaddress
import socket
from typing import Literal, Optional
from urllib.parse import urljoin, urlsplit

import requests

from bookwyrm.utils.ip_utils import check_ip_routable


MAX_REMOTE_REDIRECTS = 3


class RemoteRequestError(ValueError):
    """The requested remote URL is unsafe or cannot be resolved."""


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

    try:
        addresses = {
            result[4][0]
            for result in socket.getaddrinfo(
                hostname,
                port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        }
    except socket.gaierror as err:
        raise RemoteRequestError("Could not resolve remote hostname") from err

    if not addresses or any(not check_ip_routable(address) for address in addresses):
        raise RemoteRequestError("Remote hostname resolves to a non-public address")


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
