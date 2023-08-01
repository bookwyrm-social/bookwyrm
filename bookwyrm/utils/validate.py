"""Validations"""
from bookwyrm.settings import DOMAIN, USE_HTTPS


def validate_url_domain(url):
    """Basic check that the URL starts with the instance domain name"""
    if not url:
        return None

    if url == "/":
        return url

    protocol = "https://" if USE_HTTPS else "http://"
    origin = f"{protocol}{DOMAIN}"

    if url.startswith(origin):
        return url

    return None
