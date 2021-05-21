""" non-interactive pages """
from django.contrib.auth.decorators import login_required
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.shortcuts import redirect
from django.views import View


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class Notifications(View):
    """notifications view"""

    def get(self, request, notification_type=None):
        """people are interacting with you, get hyped"""
        notifications = request.user.notification_set.all().order_by("-created_date")
        if notification_type == "mentions":
            notifications = notifications.filter(
                notification_type__in=["REPLY", "MENTION", "TAG"]
            )
        unread = [n.id for n in notifications.filter(read=False)[:50]]
        data = {
            "notifications": notifications[:50],
            "unread": unread,
        }
        notifications.update(read=True)
        return TemplateResponse(request, "notifications.html", data)

    def post(self, request):
        """permanently delete notification for user"""
        request.user.notification_set.filter(read=True).delete()
        return redirect("/notifications")
