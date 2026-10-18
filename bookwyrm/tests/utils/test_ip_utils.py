import pytest
from collections import namedtuple

from bookwyrm.utils.ip_utils import client_ip_address


@pytest.mark.parametrize(
    "remote_address, forwarded_header, expected_address",
    [
        ("127.0.0.2", "10.2.3.4, 192.168.1.2, 193.222.12.3", "193.222.12.3"),
        ("193.223.12.3", "10.2.3.4, 192.168.1.2, 193.222.12.3", "193.222.12.3"),
        ("193.223.12.3", "10.2.3.4, 192.168.1.2", "193.223.12.3"),
        ("193.223.12.3", "10.2.3.4, 193.223.12.1, 192.168.1.2", "193.223.12.3"),
        (
            "::1",
            "fe80::32, 2a04:3540:1000:310:bc35:f2ff:fe59:7948",
            "2a04:3540:1000:310:bc35:f2ff:fe59:7948",
        ),
        (
            "::1",
            "fe80::32, 2a04:3540:1000:310:bc35:f2ff:fe59:7948, not.an.ip.address",
            "::1",
        ),
    ],
)
def test_ip_parsing(
    remote_address: str, forwarded_header: str, expected_address: str
) -> None:
    MockRequest = namedtuple("MockRequest", ["META", "headers"])

    request = MockRequest(
        META={"REMOTE_ADDR": remote_address},
        headers={"x-forwarded-for": forwarded_header},
    )

    result = client_ip_address(request)
    assert result == expected_address
