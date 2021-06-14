""" boosts and favs """
from django.db import IntegrityError
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import models


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class Favorite(View):
    """like a status"""

    def post(self, request, status_id):
        """create a like"""
        status = models.Status.objects.get(id=status_id)
        try:
            models.Favorite.objects.create(status=status, user=request.user)
        except IntegrityError:
            # you already fav'ed that
            return HttpResponseBadRequest()

        return redirect(request.headers.get("Referer", "/"))


@method_decorator(login_required, name="dispatch")
class Unfavorite(View):
    """take back a fav"""

    def post(self, request, status_id):
        """unlike a status"""
        status = models.Status.objects.get(id=status_id)
        try:
            favorite = models.Favorite.objects.get(status=status, user=request.user)
        except models.Favorite.DoesNotExist:
            # can't find that status, idk
            return HttpResponseNotFound()

        favorite.delete()
        return redirect(request.headers.get("Referer", "/"))


@method_decorator(login_required, name="dispatch")
class Boost(View):
    """boost a status"""

    def post(self, request, status_id):
        """boost a status"""
        status = models.Status.objects.get(id=status_id)
        # is it boostable?
        if not status.boostable:
            return HttpResponseBadRequest()

        if models.Boost.objects.filter(
            boosted_status=status, user=request.user
        ).exists():
            # you already boosted that.
            return redirect(request.headers.get("Referer", "/"))

        models.Boost.objects.create(
            boosted_status=status,
            privacy=status.privacy,
            user=request.user,
        )
        return redirect(request.headers.get("Referer", "/"))


@method_decorator(login_required, name="dispatch")
class Unboost(View):
    """boost a status"""

    def post(self, request, status_id):
        """boost a status"""
        status = models.Status.objects.get(id=status_id)
        boost = models.Boost.objects.filter(
            boosted_status=status, user=request.user
        ).first()

        boost.delete()
        return redirect(request.headers.get("Referer", "/"))
