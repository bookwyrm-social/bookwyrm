"""group views"""
from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.core.paginator import Paginator
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models.functions import Greatest

from bookwyrm import forms, models
from bookwyrm.suggested_users import suggested_users
from .helpers import get_user_from_username

# pylint: disable=no-self-use
class Group(View):
    """group page"""

    def get(self, request, group_id):
        """display a group"""

        group = get_object_or_404(models.Group, id=group_id)
        group.raise_visible_to_user(request.user)
        lists = (
            models.List.privacy_filter(request.user)
            .filter(group=group)
            .order_by("-updated_date")
        )

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

        # let the other members know something about the group changed
        memberships = models.GroupMember.objects.filter(group=user_group)
        model = apps.get_model("bookwyrm.Notification", require_ready=True)
        for field in form.changed_data:
            notification_type = (
                "GROUP_PRIVACY"
                if field == "privacy"
                else "GROUP_NAME"
                if field == "name"
                else "GROUP_DESCRIPTION"
                if field == "description"
                else None
            )
            if notification_type:
                for membership in memberships:
                    member = membership.user
                    if member != request.user:
                        model.objects.create(
                            user=member,
                            related_user=request.user,
                            related_group=user_group,
                            notification_type=notification_type,
                        )

        return redirect("group", user_group.id)


@method_decorator(login_required, name="dispatch")
class UserGroups(View):
    """a user's groups page"""

    def get(self, request, username):
        """display a group"""
        user = get_user_from_username(request.user, username)
        groups = (
            models.Group.privacy_filter(request.user)
            .filter(memberships__user=user)
            .order_by("-updated_date")
        )
        paginated = Paginator(groups, 12)

        data = {
            "groups": paginated.get_page(request.GET.get("page")),
            "is_self": request.user.id == user.id,
            "user": user,
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
            return redirect(request.user.local_path + "/groups")
        group = form.save()
        # add the creator as a group member
        models.GroupMember.objects.create(group=group, user=request.user)
        return redirect("group", group.id)


@method_decorator(login_required, name="dispatch")
class FindUsers(View):
    """find friends to add to your group"""

    # this is mostly borrowed from the Get Started friend finder

    def get(self, request, group_id):
        """basic profile info"""
        user_query = request.GET.get("user_query")
        group = get_object_or_404(models.Group, id=group_id)

        if not group:
            return HttpResponseBadRequest()

        if not group.user == request.user:
            return HttpResponseBadRequest()

        user_results = (
            models.User.viewer_aware_objects(request.user)
            .exclude(
                memberships__in=group.memberships.all()
            )  # don't suggest users who are already members
            .annotate(
                similarity=Greatest(
                    TrigramSimilarity("username", user_query),
                    TrigramSimilarity("localname", user_query),
                )
            )
            .filter(similarity__gt=0.5, local=True)
            .order_by("-similarity")[:5]
        )
        data = {"no_results": not user_results}

        if user_results.count() < 5:
            user_results = list(user_results) + suggested_users.get_suggestions(
                request.user, local=True
            )

        data = {
            "suggested_users": user_results,
            "group": group,
            "group_form": forms.GroupForm(instance=group),
            "user_query": user_query,
            "requestor_is_manager": request.user == group.user,
        }
        return TemplateResponse(request, "groups/find_users.html", data)


@require_POST
@login_required
def delete_group(request, group_id):
    """delete a group"""
    group = get_object_or_404(models.Group, id=group_id)

    # only the owner can delete a group
    group.raise_not_deletable(request.user)

    # deal with any group lists
    models.List.objects.filter(group=group).update(curation="closed", group=None)

    group.delete()
    return redirect(request.user.local_path + "/groups")


@require_POST
@login_required
def invite_member(request):
    """invite a member to the group"""

    group = get_object_or_404(models.Group, id=request.POST.get("group"))
    if not group:
        return HttpResponseBadRequest()

    user = get_user_from_username(request.user, request.POST["user"])
    if not user:
        return HttpResponseBadRequest()

    if not group.user == request.user:
        return HttpResponseBadRequest()

    try:
        models.GroupMemberInvitation.objects.create(user=user, group=group)

    except IntegrityError:
        pass

    return redirect(user.local_path)


@require_POST
@login_required
def remove_member(request):
    """remove a member from the group"""

    group = get_object_or_404(models.Group, id=request.POST.get("group"))
    if not group:
        return HttpResponseBadRequest()

    user = get_user_from_username(request.user, request.POST["user"])
    if not user:
        return HttpResponseBadRequest()

    # you can't be removed from your own group
    if request.POST["user"] == group.user:
        return HttpResponseBadRequest()

    is_member = models.GroupMember.objects.filter(group=group, user=user).exists()
    is_invited = models.GroupMemberInvitation.objects.filter(
        group=group, user=user
    ).exists()

    if is_invited:
        try:
            invitation = models.GroupMemberInvitation.objects.get(
                user=user, group=group
            )

            invitation.reject()

        except IntegrityError:
            pass

    if is_member:

        try:
            models.List.remove_from_group(group.user, user)
            models.GroupMember.remove(group.user, user)

        except IntegrityError:
            pass

        memberships = models.GroupMember.objects.filter(group=group)
        model = apps.get_model("bookwyrm.Notification", require_ready=True)
        notification_type = "LEAVE" if user == request.user else "REMOVE"
        # let the other members know about it
        for membership in memberships:
            member = membership.user
            if member != request.user:
                model.objects.create(
                    user=member,
                    related_user=user,
                    related_group=group,
                    notification_type=notification_type,
                )

        # let the user (now ex-member) know as well, if they were removed
        if notification_type == "REMOVE":
            model.objects.create(
                user=user,
                related_group=group,
                notification_type=notification_type,
            )

    return redirect(group.local_path)


@require_POST
@login_required
def accept_membership(request):
    """accept an invitation to join a group"""

    group = models.Group.objects.get(id=request.POST["group"])
    if not group:
        return HttpResponseBadRequest()

    invite = models.GroupMemberInvitation.objects.get(group=group, user=request.user)
    if not invite:
        return HttpResponseBadRequest()

    try:
        invite.accept()

    except IntegrityError:
        pass

    return redirect(group.local_path)


@require_POST
@login_required
def reject_membership(request):
    """reject an invitation to join a group"""

    group = models.Group.objects.get(id=request.POST["group"])
    if not group:
        return HttpResponseBadRequest()

    invite = models.GroupMemberInvitation.objects.get(group=group, user=request.user)
    if not invite:
        return HttpResponseBadRequest()

    try:
        invite.reject()

    except IntegrityError:
        pass

    return redirect(request.user.local_path)
