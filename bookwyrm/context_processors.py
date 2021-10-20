""" customize the info available in context for rendering templates """
from bookwyrm import models, settings


def site_settings(request):  # pylint: disable=unused-argument
    """include the custom info about the site"""
    request_protocol = "https://"
    if not request.is_secure():
        request_protocol = "http://"

    return {
        "site": models.SiteSettings.objects.get(),
        "active_announcements": models.Announcement.active_announcements(),
        "thumbnail_generation_enabled": settings.ENABLE_THUMBNAIL_GENERATION,
        "media_full_url": settings.MEDIA_FULL_URL,
        "preview_images_enabled": settings.ENABLE_PREVIEW_IMAGES,
        "request_protocol": request_protocol,
        "js_cache": settings.JS_CACHE,
    }
