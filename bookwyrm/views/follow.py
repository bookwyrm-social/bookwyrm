""" views for actions you can take in the application """
import urllib.parse
import re
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.views.decorators.http import require_POST

from bookwyrm import models
from .helpers import get_user_from_username, handle_remote_webfinger


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
    username_parts = re.search("(?:^http(?:s?):\/\/)([\w\-\.]*)(?:.)*(?:(?:\/)([\w]*))", uri)
    account = f"{username_parts[2]}@{username_parts[1]}"
    user = handle_remote_webfinger(account)
    error = None

    if user is None or user == "":
        error = "ostatus_subscribe"

    if bool(user) and user in request.user.blocks.all():
        error = "is_blocked"

    if hasattr(user, "followers") and request.user in user.followers.all():
        error = "already_following"

    if hasattr(user, "follower_requests") and request.user in user.follower_requests.all():
        error = "already_requested"

    data = {
        "account": account,
        "user": user,
        "error": error
    }

    return TemplateResponse(request, "ostatus/subscribe.html", data)


@login_required
def ostatus_follow_success(request):
    """display success message for remote follow"""
    user = get_user_from_username(request.user, request.GET.get("following"))
    data = {
        "account": user.name,
        "user": user, 
        "error": None
    }
    return TemplateResponse(request, "ostatus/success.html", data)

@login_required
@require_POST
def remote_follow(request):
    """complete an incoming remote follow request"""

    # this is triggered from remote follow form
    # attempt the follow request
    # on success [[return success page]]
    # on fail return [[ostatus_error]]


"""
REQUEST TO FOLLOW FROM REMOTE ACCOUNT
1. click remote follow button [default checked option to open new window]
2. popup new small window
3. enter user acct to follow from (user@domain.tld) and submit form 
5. GET {base_url}/.well-known/webfinger/?resource=acct:{user@domain.tld}
6. parse json for links 
6.1 rel="http://ostatus.org/schema/1.0/subscribe" and return 'template'
6.2 rel="self" and return href
7. replace '{uri}' in the returned string with self.href
8. GET the URI at 6.1

REQUEST TO FOLLOW FROM LOCAL ACCOUNT
1. receive request to /ostatus_subscribe?acct={uri}
2. check user is logged in and present confirmation screen (remote_follow_request)
3. On confirmation, 3. parse user into info needed for a normal follow
4. send follow request, on 200 response display success else display error (remote_follow)
5. Include button inviting to close window
"""
