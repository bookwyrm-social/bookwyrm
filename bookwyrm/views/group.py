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
from .helpers import privacy_filter
from .helpers import get_user_from_username

class Group(View):
    """group page"""

    def get(self, request, group_id):
        """display a group"""

        group = models.Group.objects.get(id=group_id) 
        # groups = privacy_filter(
        #     request.user, groups, privacy_levels=["public", "followers"]
        # )


        data = {
            "group": group,
            "list_form": forms.GroupForm(),
            "path": "/group",
        }
        return TemplateResponse(request, "groups/group.html", data)

@method_decorator(login_required, name="dispatch")
class UserGroups(View):
    """a user's groups page"""

    def get(self, request, username):
        """display a group"""
        user = get_user_from_username(request.user, username)
        groups = models.Group.objects.filter(members=user).order_by("-updated_date")
        paginated = Paginator(groups, 12)

        data = {
            "user": user,
            "is_self": request.user.id == user.id,
            "groups": paginated.get_page(request.GET.get("page")),
            "group_form": forms.GroupForm(),
            "path": user.local_path + "/group",
        }
        return TemplateResponse(request, "user/groups.html", data)

@login_required
@require_POST
def create_group(request):
    """user groups"""
    form = forms.GroupForm(request.POST)
    if not form.is_valid():
        print("invalid!")
        return redirect(request.headers.get("Referer", "/"))

    group = form.save()
    # TODO: add user as group member
    models.GroupMember.objects.create(group=group, user=request.user)
    return redirect(group.local_path)