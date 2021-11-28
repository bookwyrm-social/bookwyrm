""" views for actions you can take in the application """
import urllib.parse
import re
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.views.decorators.http import require_POST

from bookwyrm import models
from .helpers import (
    get_user_from_username,
    handle_remote_webfinger,
    subscribe_remote_webfinger,
)


@login_required
@require_POST
def follow(request):
    """follow another user, here or abroad"""
    username = request.POST["user"]
    to_follow = get_user_from_username(request.user, username)

    try:
        models.UserFollowRequest.objects.create(
            user_subject=request.user,
            user_object=to_follow,
        )
    except IntegrityError:
        pass

    if request.GET.get("next"):
        return redirect(request.GET.get("next", "/"))

    return redirect(to_follow.local_path)


@login_required
@require_POST
def unfollow(request):
    """unfollow a user"""
    username = request.POST["user"]
    to_unfollow = get_user_from_username(request.user, username)

    try:
        models.UserFollows.objects.get(
            user_subject=request.user, user_object=to_unfollow
        ).delete()
    except models.UserFollows.DoesNotExist:
        pass

    try:
        models.UserFollowRequest.objects.get(
            user_subject=request.user, user_object=to_unfollow
        ).delete()
    except models.UserFollowRequest.DoesNotExist:
        pass

    # this is handled with ajax so it shouldn't really matter
    return redirect(request.headers.get("Referer", "/"))


@login_required
@require_POST
def accept_follow_request(request):
    """a user accepts a follow request"""
    username = request.POST["user"]
    requester = get_user_from_username(request.user, username)

    try:
        follow_request = models.UserFollowRequest.objects.get(
            user_subject=requester, user_object=request.user
        )
    except models.UserFollowRequest.DoesNotExist:
        # Request already dealt with.
        return redirect(request.user.local_path)
    follow_request.accept()

    return redirect(request.user.local_path)


@login_required
@require_POST
def delete_follow_request(request):
    """a user rejects a follow request"""
    username = request.POST["user"]
    requester = get_user_from_username(request.user, username)

    follow_request = get_object_or_404(
        models.UserFollowRequest, user_subject=requester, user_object=request.user
    )
    follow_request.raise_not_deletable(request.user)

    follow_request.delete()
    return redirect(f"/user/{request.user.localname}")


def ostatus_follow_request(request):
    """prepare an outgoing remote follow request"""

    # parse the acct URI into a user string
    uri = urllib.parse.unquote(request.GET.get("acct"))
    username_parts = re.search(
        "(?:^http(?:s?):\/\/)([\w\-\.]*)(?:.)*(?:(?:\/)([\w]*))", uri
    )
    account = f"{username_parts[2]}@{username_parts[1]}"
    user = handle_remote_webfinger(account)
    error = None

    if user is None or user == "":
        error = "ostatus_subscribe"

    if bool(user) and user in request.user.blocks.all():
        error = "is_blocked"

    if hasattr(user, "followers") and request.user in user.followers.all():
        error = "already_following"

    if (
        hasattr(user, "follower_requests")
        and request.user in user.follower_requests.all()
    ):
        error = "already_requested"

    data = {"account": account, "user": user, "error": error}

    return TemplateResponse(request, "ostatus/subscribe.html", data)


@login_required
def ostatus_follow_success(request):
    """display success message for remote follow"""
    user = get_user_from_username(request.user, request.GET.get("following"))
    data = {"account": user.name, "user": user, "error": None}
    return TemplateResponse(request, "ostatus/success.html", data)


def remote_follow_page(request):
    """Display remote follow page"""
    user = get_user_from_username(request.user, request.GET.get("user"))
    data = {"user": user}
    return TemplateResponse(request, "ostatus/remote_follow.html", data)


@require_POST
def remote_follow(request):
    """direct user to follow from remote account using ostatus subscribe protocol"""
    remote_user = request.POST.get("remote_user")
    template = subscribe_remote_webfinger(remote_user)
    url = template.replace("{uri}", request.POST.get("user"))
    return redirect(url)
