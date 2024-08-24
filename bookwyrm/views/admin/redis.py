""" redis cache status """
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
import redis

from bookwyrm import models, settings

r = redis.from_url(settings.REDIS_ACTIVITY_URL)

# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_instance_settings", raise_exception=True),
    name="dispatch",
)
class RedisStatus(View):
    """Are your tasks running? Well you'd better go catch them"""

    def get(self, request):
        """See workers and active tasks"""
        data = {"errors": []}
        try:
            data["info"] = r.info
        # pylint: disable=broad-except
        except Exception as err:
            data["errors"].append(err)

        return TemplateResponse(request, "settings/redis.html", data)

    # pylint: disable=unused-argument
    def post(self, request):
        """Erase invalid keys"""
        dry_run = request.POST.get("dry_run")
        patterns = [":*:*"]  # this pattern is a django cache with no prefix
        for user_id in models.User.objects.filter(
            is_deleted=True, local=True
        ).values_list("id", flat=True):
            patterns.append(f"{user_id}-*")

        deleted_count = 0
        for pattern in patterns:
            deleted_count += erase_keys(pattern, dry_run=dry_run)

        if dry_run:
            return HttpResponse(f"{deleted_count} keys identified for deletion")
        return HttpResponse(f"{deleted_count} keys deleted")


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
