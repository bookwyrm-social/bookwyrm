import ipaddress

from django.http import HttpRequest


def check_ip_routable(remote_address: str) -> bool:
    """
    Checks if given address is public address and usable in blocking

    """

    """ ipaddress has these fixed in 3.13 python, but we are not there yet"""
    ACTUALLY_PRIVATE_RANGES = [
        ipaddress.ip_network("192.0.0.0/24"),
        ipaddress.ip_network("64:ff9b:1::/48"),
        ipaddress.ip_network("2002::/16"),
    ]
    ACTUALLY_PUBLIC_RANGES = [
        ipaddress.ip_network("192.0.0.9/32"),
        ipaddress.ip_network("192.0.0.10/32"),
        ipaddress.ip_network("2001:1::1/128"),
        ipaddress.ip_network("2001:1::2/128"),
        ipaddress.ip_network("2001:3::/32"),
        ipaddress.ip_network("2001:4:112::/48"),
        ipaddress.ip_network("2001:20::/28"),
        ipaddress.ip_network("2001:30::/28"),
    ]

    try:
        parsed_address = ipaddress.ip_address(remote_address)
        if parsed_address.is_global:
            for network_range in ACTUALLY_PRIVATE_RANGES:
                if parsed_address in network_range:
                    return False
            return True
        if parsed_address.is_private:
            for network_range in ACTUALLY_PUBLIC_RANGES:
                if parsed_address in network_range:
                    return True
        return False

    except (ipaddress.AddressValueError, ValueError):
        # Non valid ip-address is not routable is safe default
        return False


def client_ip_address(request: HttpRequest) -> str:
    """

    checks client-ip address and x-forwarded-for header if present.
    for x-forwarded-for addresses, picks first that is public address.
    Checking from right to left.

    Rightmost should come from our nginx and we stop in first non-routable address and pick one previous to that.

    """
    address: str = request.META.get("REMOTE_ADDR", "")
    if forward_header := request.headers.get("x-forwarded-for"):
        for remote_address in reversed(forward_header.split(", ")):
            if check_ip_routable(remote_address):
                address = remote_address
                continue
            break
    return address
