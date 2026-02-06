"""redis cache status"""

from django.contrib.auth.decorators import login_required, permission_required
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
import redis

from bookwyrm import models, settings

r = redis.from_url(settings.REDIS_ACTIVITY_URL)


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_instance_settings", raise_exception=True),
    name="dispatch",
)
class RedisStatus(View):
    """Are your tasks running? Well you'd better go catch them"""

    def get(self, request):
        """See workers and active tasks"""
        data = view_data()

        return TemplateResponse(request, "settings/redis.html", data)

    def post(self, request):
        """Erase invalid keys"""
        dry_run = request.POST.get("dry_run")
        erase_cache = request.POST.get("erase_cache")
        data_key = "cache" if erase_cache else "outdated"

        if erase_cache:
            patterns = [f"{settings.CACHE_KEY_PREFIX}:*:*"]
        else:
            patterns = [":*:*"]  # this pattern is a django cache with no prefix
            for user_id in models.User.objects.filter(
                is_deleted=True, local=True
            ).values_list("id", flat=True):
                patterns.append(f"{user_id}-*")

        deleted_count = 0
        for pattern in patterns:
            deleted_count += erase_keys(pattern, dry_run=dry_run)

        data = view_data()
        if dry_run:
            data[f"{data_key}_identified"] = deleted_count
        else:
            data[f"{data_key}_deleted"] = deleted_count
        return TemplateResponse(request, "settings/redis.html", data)


def view_data():
    """Helper function to load basic info for the view"""
    data = {"errors": [], "prefix": settings.CACHE_KEY_PREFIX}
    try:
        data["info"] = r.info()
    except Exception as err:
        data["errors"].append(err)
    return data


def erase_keys(pattern, count=1000, dry_run=False):
    """Delete all redis activity keys according to a provided regex pattern"""
    pipeline = r.pipeline()
    key_count = 0
    for key in r.scan_iter(match=pattern, count=count):
        key_count += 1
        if dry_run:
            continue
        pipeline.delete(key)
    if not dry_run:
        pipeline.execute()
    return key_count
