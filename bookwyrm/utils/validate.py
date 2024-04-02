"""Validations"""
from typing import Optional

from bookwyrm.settings import DOMAIN, USE_HTTPS


def validate_url_domain(url: Optional[str]) -> Optional[str]:
    """Basic check that the URL starts with the instance domain name"""
    if url is None:
        return None

    protocol = "https://" if USE_HTTPS else "http://"
    origin = f"{protocol}{DOMAIN}"

    if url.startswith(origin):
        return url

    return None
