""" views for actions you can take in the application """
import urllib.parse
import re

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.views.decorators.http import require_POST

from bookwyrm import models
from bookwyrm.models.relationship import clear_cache
from .helpers import (
    get_user_from_username,
    handle_remote_webfinger,
    subscribe_remote_webfinger,
    WebFingerError,
    is_api_request,
)


@login_required
@require_POST
def follow(request):
    """follow another user, here or abroad"""
    username = request.POST["user"]
    to_follow = get_user_from_username(request.user, username)
    clear_cache(request.user, to_follow)

    follow_request, created = models.UserFollowRequest.objects.get_or_create(
        user_subject=request.user,
        user_object=to_follow,
    )

    if not created:
        # this request probably failed to connect with the remote
        # that means we should save to trigger a re-broadcast
        follow_request.save()

    if is_api_request(request):
        return HttpResponse()
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
        clear_cache(request.user, to_unfollow)

    try:
        models.UserFollowRequest.objects.get(
            user_subject=request.user, user_object=to_unfollow
        ).delete()
    except models.UserFollowRequest.DoesNotExist:
        clear_cache(request.user, to_unfollow)

    if is_api_request(request):
        return HttpResponse()
    # this is handled with ajax so it shouldn't really matter
    return redirect("/")


@login_required
@require_POST
def remove_follow(request, user_id):
    """remove a previously approved follower without blocking them"""

    to_remove = get_object_or_404(models.User, id=user_id)

    try:
        models.UserFollows.objects.get(
            user_subject=to_remove, user_object=request.user
        ).reject()
    except models.UserFollows.DoesNotExist:
        clear_cache(to_remove, request.user)

    try:
        models.UserFollowRequest.objects.get(
            user_subject=to_remove, user_object=request.user
        ).reject()
    except models.UserFollowRequest.DoesNotExist:
        clear_cache(to_remove, request.user)

    if is_api_request(request):
        return HttpResponse()

    return redirect(f"{request.user.local_path}/followers")


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

    follow_request.reject()
    return redirect(f"/user/{request.user.localname}")


def ostatus_follow_request(request):
    """prepare an outgoing remote follow request"""
    uri = urllib.parse.unquote(request.GET.get("acct"))
    username_parts = re.search(
        r"(?:^http(?:s?):\/\/)([\w\-\.]*)(?:.)*(?:(?:\/)([\w]*))", uri
    )
    account = f"{username_parts[2]}@{username_parts[1]}"
    user = handle_remote_webfinger(account)
    error = None

    if user is None or user == "":
        error = "ostatus_subscribe"

    # don't do these checks for AnonymousUser before they sign in
    if request.user.is_authenticated:

        # you have blocked them so you probably don't want to follow
        if hasattr(request.user, "blocks") and user in request.user.blocks.all():
            error = "is_blocked"
        # they have blocked you
        if hasattr(user, "blocks") and request.user in user.blocks.all():
            error = "has_blocked"
        # you're already following them
        if hasattr(user, "followers") and request.user in user.followers.all():
            error = "already_following"
        # you're not following yet but you already asked
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
    """display remote follow page"""
    user = get_user_from_username(request.user, request.GET.get("user"))
    data = {"user": user}
    return TemplateResponse(request, "ostatus/remote_follow.html", data)


@require_POST
def remote_follow(request):
    """direct user to follow from remote account using ostatus subscribe protocol"""
    remote_user = request.POST.get("remote_user")
    try:
        if remote_user[0] == "@":
            remote_user = remote_user[1:]
        remote_domain = remote_user.split("@")[1]
    except (TypeError, IndexError):
        remote_domain = None

    wf_response = subscribe_remote_webfinger(remote_user)
    user = get_object_or_404(models.User, id=request.POST.get("user"))

    if wf_response is None:
        data = {
            "account": remote_user,
            "user": user,
            "error": "not_supported",
            "remote_domain": remote_domain,
        }
        return TemplateResponse(request, "ostatus/subscribe.html", data)

    if isinstance(wf_response, WebFingerError):
        data = {
            "account": remote_user,
            "user": user,
            "error": str(wf_response),
            "remote_domain": remote_domain,
        }
        return TemplateResponse(request, "ostatus/subscribe.html", data)

    url = wf_response.replace("{uri}", urllib.parse.quote(user.remote_id))
    return redirect(url)
