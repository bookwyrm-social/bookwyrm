""" customize the info available in context for rendering templates """
from bookwyrm import models, settings


def site_settings(request):
    """include the custom info about the site"""
    request_protocol = "https://"
    if not request.is_secure():
        request_protocol = "http://"

    site = models.SiteSettings.objects.get()
    theme = "css/themes/bookwyrm-light.scss"
    if (
        hasattr(request, "user")
        and request.user.is_authenticated
        and request.user.theme
    ):
        theme = request.user.theme.path
    elif site.default_theme:
        theme = site.default_theme.path

    return {
        "site": site,
        "site_theme": theme,
        "active_announcements": models.Announcement.active_announcements(),
        "thumbnail_generation_enabled": settings.ENABLE_THUMBNAIL_GENERATION,
        "media_full_url": settings.MEDIA_FULL_URL,
        "preview_images_enabled": settings.ENABLE_PREVIEW_IMAGES,
        "request_protocol": request_protocol,
        "js_cache": settings.JS_CACHE,
    }
