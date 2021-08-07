""" What's up locally """
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import models
from bookwyrm.settings import PAGE_LENGTH
from .helpers import privacy_filter


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class Discover(View):
    """preview of recently reviewed books"""

    def get(self, request):
        """tiled book activity page"""
        activities = privacy_filter(
            request.user,
            models.Status.objects.select_subclasses().filter(
                Q(comment__isnull=False)
                | Q(review__isnull=False)
                | Q(quotation__isnull=False),
                user__local=True
            ),
            #privacy_levels=["public"]
        )
        #paginated = Paginator(activities, PAGE_LENGTH)
        data = {
            "large": activities.filter(~Q(review__isnull=True, review__content=None))[:2],
            "small": activities.filter(~Q(content=None))[:4],
        }
        return TemplateResponse(request, "discover/discover.html", data)
