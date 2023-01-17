"""Validations"""
from bookwyrm.settings import DOMAIN, USE_HTTPS


def validate_url_domain(url, default="/"):
    """Basic check that the URL starts with the instance domain name"""
    if not url:
        return default

    if url in ("/", default):
        return url

    protocol = "https://" if USE_HTTPS else "http://"
    origin = f"{protocol}{DOMAIN}"

    if url.startswith(origin):
        return url

    return default
