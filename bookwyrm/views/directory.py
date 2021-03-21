""" who all's here? """
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.template.response import TemplateResponse
from django.views import View
from django.utils.decorators import method_decorator

from bookwyrm import models

# pylint: disable=no-self-use
@method_decorator(login_required, name="dispatch")
class Directory(View):
    """ display of known bookwyrm users """

    def get(self, request):
        """ lets see your cute faces """
        try:
            page = int(request.GET.get("page", 1))
        except ValueError:
            page = 1

        users = models.User.objects.filter(
            discoverable=True,
            bookwyrm_user=True,
            is_active=True,
        ).order_by("-last_active_date")
        paginated = Paginator(users, 12)

        data = {
            "users": paginated.page(page),
        }
        return TemplateResponse(request, "directory.html", data)
