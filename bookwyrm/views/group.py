"""group views"""
from typing import Optional
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, DecimalField, Q, Max
from django.db.models.functions import Coalesce
from django.http import HttpResponseNotFound, HttpResponseBadRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import forms, models
from bookwyrm.connectors import connector_manager
from bookwyrm.settings import PAGE_LENGTH
from .helpers import is_api_request, privacy_filter
from .helpers import get_user_from_username

@method_decorator(login_required, name="dispatch")
class UserGroups(View):
    """a user's groups page"""

    def get(self, request, username):
        """display a group"""
        user = get_user_from_username(request.user, username)
        groups = models.GroupMember.objects.filter(user=user)
        # groups = privacy_filter(request.user, groups)
        paginated = Paginator(groups, 12)

        data = {
            "user": user,
            "is_self": request.user.id == user.id,
            "groups": paginated.get_page(request.GET.get("page")),
            "group_form": forms.GroupsForm(),
            "path": user.local_path + "/groups",
        }
        return TemplateResponse(request, "user/groups.html", data)

# @require_POST
# @login_required
# def save_list(request, group_id):
#     """save a group"""
#     group = get_object_or_404(models.Group, id=group_id)
#     request.user.saved_group.add(group)
#     return redirect("user", request.user.id) # TODO: change this to group page