''' boosts and favs '''
from django.db import IntegrityError
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import models
from bookwyrm.broadcast import broadcast
from bookwyrm.status import create_notification


# pylint: disable= no-self-use
@method_decorator(login_required, name='dispatch')
class Favorite(View):
    ''' like a status '''
    def post(self, request, status_id):
        ''' create a like '''
        status = models.Status.objects.get(id=status_id)
        try:
            favorite = models.Favorite.objects.create(
                status=status,
                user=request.user
            )
        except IntegrityError:
            # you already fav'ed that
            return HttpResponseBadRequest()

        fav_activity = favorite.to_activity()
        broadcast(
            request.user, fav_activity, privacy='direct',
            direct_recipients=[status.user])
        if status.user.local:
            create_notification(
                status.user,
                'FAVORITE',
                related_user=request.user,
                related_status=status
            )
        return redirect(request.headers.get('Referer', '/'))


@method_decorator(login_required, name='dispatch')
class Unfavorite(View):
    ''' take back a fav '''
    def post(self, request, status_id):
        ''' unlike a status '''
        status = models.Status.objects.get(id=status_id)
        try:
            favorite = models.Favorite.objects.get(
                status=status,
                user=request.user
            )
        except models.Favorite.DoesNotExist:
            # can't find that status, idk
            return HttpResponseNotFound()

        fav_activity = favorite.to_undo_activity(request.user)
        favorite.delete()
        broadcast(request.user, fav_activity, direct_recipients=[status.user])

        # check for notification
        if status.user.local:
            notification = models.Notification.objects.filter(
                user=status.user, related_user=request.user,
                related_status=status, notification_type='FAVORITE'
            ).first()
            if notification:
                notification.delete()
        return redirect(request.headers.get('Referer', '/'))


@method_decorator(login_required, name='dispatch')
class Boost(View):
    ''' boost a status '''
    def post(self, request, status_id):
        ''' boost a status '''
        status = models.Status.objects.get(id=status_id)
        # is it boostable?
        if not status.boostable:
            return HttpResponseBadRequest()

        if models.Boost.objects.filter(
                boosted_status=status, user=request.user).exists():
            # you already boosted that.
            return redirect(request.headers.get('Referer', '/'))

        boost = models.Boost.objects.create(
            boosted_status=status,
            privacy=status.privacy,
            user=request.user,
        )

        boost_activity = boost.to_activity()
        broadcast(request.user, boost_activity)

        if status.user.local:
            create_notification(
                status.user,
                'BOOST',
                related_user=request.user,
                related_status=status
            )
        return redirect(request.headers.get('Referer', '/'))



@method_decorator(login_required, name='dispatch')
class Unboost(View):
    ''' boost a status '''
    def post(self, request, status_id):
        ''' boost a status '''
        status = models.Status.objects.get(id=status_id)
        boost = models.Boost.objects.filter(
            boosted_status=status, user=request.user
        ).first()
        activity = boost.to_undo_activity(request.user)

        boost.delete()
        broadcast(request.user, activity)

        # delete related notification
        if status.user.local:
            notification = models.Notification.objects.filter(
                user=status.user, related_user=request.user,
                related_status=status, notification_type='BOOST'
            ).first()
            if notification:
                notification.delete()
        return redirect(request.headers.get('Referer', '/'))
