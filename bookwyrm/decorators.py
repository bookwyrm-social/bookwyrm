"""Custom view decorators"""

from functools import wraps
from bookwyrm.models.site import SiteSettings


def require_federation(function):
    """Ensure that federation is allowed before proceeding with this view"""

    @wraps(function)
    def wrap(request, *args, **kwargs):
        SiteSettings.raise_federation_disabled()
        return function(request, *args, **kwargs)

    return wrap
