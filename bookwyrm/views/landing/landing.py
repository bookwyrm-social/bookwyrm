""" non-interactive pages """
from dateutil.relativedelta import relativedelta
from django.db.models import Avg, StdDev, Count, F, Q
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_GET

from bookwyrm import forms, models, settings
from bookwyrm.views import helpers
from bookwyrm.views.feed import Feed


@require_GET
def about(request):
    """more information about the instance"""
    six_months_ago = timezone.now() - relativedelta(months=6)
    six_month_count = models.User.objects.filter(
        is_active=True, local=True, last_active_date__gt=six_months_ago
    ).count()
    data = {
        "active_users": six_month_count,
        "status_count": models.Status.objects.filter(
            user__local=True, deleted=False
        ).count(),
        "admins": models.User.objects.filter(groups__name__in=["admin", "moderator"]),
        "version": settings.VERSION,
    }

    books = models.Edition.objects.exclude(cover__exact="")

    total_ratings = models.Review.objects.filter(user__local=True).count()
    data["top_rated"] = books.annotate(
        rating=Avg("review__rating", filter=Q(review__user__local=True)),
        rating_count=Count("review__rating", filter=Q(review__user__local=True)),
    ).annotate(
        weighted=F("rating") * F("rating_count") / total_ratings
    ).filter(weighted__gt=0).order_by("-weighted").first()

    data["controversial"] = books.annotate(
        deviation=StdDev("review__rating", filter=Q(review__user__local=True)),
        rating_count=Count("review__rating", filter=Q(review__user__local=True)),
    ).annotate(
        weighted=F("deviation") * F("rating_count") / total_ratings
    ).filter(weighted__gt=0).order_by("-weighted").first()

    data["wanted"] = books.annotate(
        shelf_count=Count("shelves", filter=Q(shelves__identifier="to-read"))
    ).order_by("-shelf_count").first()

    return TemplateResponse(request, "about/about.html", data)


@require_GET
def conduct(request):
    """more information about the instance"""
    return TemplateResponse(request, "about/conduct.html")


@require_GET
def privacy(request):
    """more information about the instance"""
    return TemplateResponse(request, "about/privacy.html")


# pylint: disable= no-self-use
class Home(View):
    """landing page or home feed depending on auth"""

    def get(self, request):
        """this is the same as the feed on the home tab"""
        if request.user.is_authenticated:
            feed_view = Feed.as_view()
            return feed_view(request, "home")
        landing_view = Landing.as_view()
        return landing_view(request)


class Landing(View):
    """preview of recently reviewed books"""

    def get(self, request):
        """tiled book activity page"""
        data = {
            "register_form": forms.RegisterForm(),
            "request_form": forms.InviteRequestForm(),
            "books": helpers.get_landing_books(),
        }
        return TemplateResponse(request, "landing/landing.html", data)
