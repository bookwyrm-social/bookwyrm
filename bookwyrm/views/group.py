"""group views"""
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.core.paginator import Paginator
from django.http import HttpResponseNotFound, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models.functions import Greatest

from bookwyrm import forms, models
from bookwyrm.suggested_users import suggested_users
from .helpers import privacy_filter
from .helpers import get_user_from_username
from bookwyrm.settings import DOMAIN

class Group(View):
    """group page"""

    def get(self, request, group_id):
        """display a group"""

        group = get_object_or_404(models.Group, id=group_id)
        lists = models.List.objects.filter(group=group).order_by("-updated_date")
        lists = privacy_filter(request.user, lists)

        # don't show groups to users who shouldn't see them
        if not group.visible_to_user(request.user):
            return HttpResponseNotFound()

        data = {
            "group": group,
            "lists": lists,
            "group_form": forms.GroupForm(instance=group),
            "path": "/group",
        }
        return TemplateResponse(request, "groups/group.html", data)

    @method_decorator(login_required, name="dispatch")
    def post(self, request, group_id):
        """edit a group"""
        user_group = get_object_or_404(models.Group, id=group_id)
        form = forms.GroupForm(request.POST, instance=user_group)
        if not form.is_valid():
            return redirect("group", user_group.id)
        user_group = form.save()
        return redirect("group", user_group.id) 

@method_decorator(login_required, name="dispatch")
class UserGroups(View):
    """a user's groups page"""

    def get(self, request, username):
        """display a group"""
        user = get_user_from_username(request.user, username)
        groups = models.Group.objects.filter(members=user).order_by("-updated_date")
        # groups = privacy_filter(request.user, groups)
        paginated = Paginator(groups, 12)

        data = {
            "user": user,
            "has_groups": models.GroupMember.objects.filter(user=user).exists(),
            "groups": paginated.get_page(request.GET.get("page")),
            "group_form": forms.GroupForm(),
            "path": user.local_path + "/group",
        }
        return TemplateResponse(request, "user/groups.html", data)

    @method_decorator(login_required, name="dispatch")
    # pylint: disable=unused-argument
    def post(self, request, username):
        """create a user group"""
        form = forms.GroupForm(request.POST)
        if not form.is_valid():
            return redirect(request.user.local_path + "groups")
        group = form.save()
        # add the creator as a group member
        models.GroupMember.objects.create(group=group, user=request.user)
        return redirect("group", group.id)

@method_decorator(login_required, name="dispatch")
class FindUsers(View):
    """find friends to add to your group"""
    """this is mostly taken from the Get Started friend finder"""

    def get(self, request, group_id):
        """basic profile info"""
        query = request.GET.get("query")
        user_results = (
            models.User.viewer_aware_objects(request.user)
            .annotate(
                similarity=Greatest(
                    TrigramSimilarity("username", query),
                    TrigramSimilarity("localname", query),
                )
            )
            .filter(
                similarity__gt=0.5,
            )
            .order_by("-similarity")[:5]
        )
        data = {"no_results": not user_results}

        if user_results.count() < 5:
            user_results = list(user_results) + suggested_users.get_suggestions(
                request.user
            )

        group = get_object_or_404(models.Group, id=group_id)

        data["suggested_users"] = user_results
        data["group"] = group
        data["query"] = query
        data["requestor_is_manager"] = request.user == group.user
        return TemplateResponse(request, "groups/find_users.html", data)

@require_POST
@login_required
def add_member(request):
    """add a member to the group"""

    # TODO: if groups become AP values we need something like get_group_from_group_fullname
    group = get_object_or_404(models.Group, id=request.POST.get("group"))
    if not group:
        return HttpResponseBadRequest()

    user = get_user_from_username(request.user, request.POST["user"])
    if not user:
        return HttpResponseBadRequest()

    if not group.user == request.user:
        return HttpResponseBadRequest()

    try:
        models.GroupMember.objects.create(
          group=group,
          user=user
        )

    except IntegrityError:
        pass

    return redirect(user.local_path)

@require_POST
@login_required
def remove_member(request):
    """remove a member from the group"""

    # TODO: if groups become AP values we need something like get_group_from_group_fullname
    # group = get_object_or_404(models.Group, id=request.POST.get("group"))
    group = models.Group.objects.get(id=request.POST["group"])
    if not group:
        return HttpResponseBadRequest()

    user = get_user_from_username(request.user, request.POST["user"])
    if not user:
        return HttpResponseBadRequest()

    if not group.user == request.user:
        return HttpResponseBadRequest()

    try:
        membership = models.GroupMember.objects.get(group=group,user=user)
        membership.delete()

    except IntegrityError:
        print("no integrity")
        pass

    return redirect(user.local_path)