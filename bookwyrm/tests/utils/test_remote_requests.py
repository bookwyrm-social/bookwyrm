"""Tests for safe remote request handling."""

import socket
from unittest.mock import patch

import pytest
import responses

from bookwyrm.utils.remote_requests import (
    REMOTE_URL_CACHE_TTL,
    RemoteRequestError,
    get_remote_response,
    validate_remote_url,
)


def dns_result(address):
    """Return one getaddrinfo result for an address."""
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]


def test_validate_remote_url_allows_public_address():
    """Public hostnames can be fetched."""
    with patch(
        "bookwyrm.utils.remote_requests.socket.getaddrinfo",
        return_value=dns_result("93.184.216.34"),
    ):
        validate_remote_url("https://example.com/actor")


def test_validate_remote_url_caches_recent_lookup():
    """Recent DNS lookups are reused for the same host and port."""
    with patch(
        "bookwyrm.utils.remote_requests.socket.getaddrinfo",
        return_value=dns_result("93.184.216.34"),
    ) as getaddrinfo:
        validate_remote_url("https://cached.example/actor")
        validate_remote_url("https://cached.example/another-actor")

    getaddrinfo.assert_called_once()


def test_validate_remote_url_refreshes_expired_lookup():
    """DNS is resolved again when the cache entry expires."""
    with (
        patch(
            "bookwyrm.utils.remote_requests.socket.getaddrinfo",
            return_value=dns_result("93.184.216.34"),
        ) as getaddrinfo,
        patch(
            "bookwyrm.utils.remote_requests.monotonic",
            side_effect=[0, REMOTE_URL_CACHE_TTL + 1],
        ),
    ):
        validate_remote_url("https://expired.example/actor")
        validate_remote_url("https://expired.example/another-actor")

    assert getaddrinfo.call_count == 2


@pytest.mark.parametrize("address", ["127.0.0.1", "169.254.169.254", "::1"])
def test_validate_remote_url_rejects_non_public_address(address):
    """Hostnames resolving internally must not be fetched."""
    with patch(
        "bookwyrm.utils.remote_requests.socket.getaddrinfo",
        return_value=dns_result(address),
    ):
        with pytest.raises(RemoteRequestError):
            validate_remote_url("https://remote.example/actor")


@responses.activate
def test_get_remote_response_rejects_private_redirect():
    """Redirects are checked before a second request is made."""
    responses.add(
        responses.GET,
        "https://public.example/actor",
        status=302,
        headers={"Location": "https://private.example/metadata"},
    )

    def resolve_host(hostname, *_args, **_kwargs):
        address = "93.184.216.34" if hostname == "public.example" else "127.0.0.1"
        return dns_result(address)

    with patch(
        "bookwyrm.utils.remote_requests.socket.getaddrinfo",
        side_effect=resolve_host,
    ):
        with pytest.raises(RemoteRequestError):
            get_remote_response("https://public.example/actor", headers={}, timeout=5)

    assert len(responses.calls) == 1
