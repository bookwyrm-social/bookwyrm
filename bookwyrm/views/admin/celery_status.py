""" manage site settings """
from django.contrib.auth.decorators import login_required, permission_required
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm.tasks import app as celery


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_instance_settings", raise_exception=True),
    name="dispatch",
)
class CeleryStatus(View):
    """manage things like the instance name"""

    def get(self, request):
        """edit form"""
        inspect = celery.control.inspect()
        data = {"stats": inspect.stats(), "active_tasks": inspect.active()}
        return TemplateResponse(request, "settings/celery.html", data)
