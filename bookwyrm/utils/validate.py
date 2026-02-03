"""Validations"""

from typing import Optional

from bookwyrm.settings import BASE_URL


def validate_url_domain(url: Optional[str]) -> Optional[str]:
    """Basic check that the URL starts with the instance domain name"""
    if url is None:
        return None

    if not url.startswith(BASE_URL):
        return None

    return url
