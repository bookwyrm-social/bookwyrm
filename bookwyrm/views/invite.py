""" invites when registration is closed """
from functools import reduce
import operator
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import emailing, forms, models
from bookwyrm.settings import PAGE_LENGTH
from . import helpers


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.create_invites", raise_exception=True),
    name="dispatch",
)
class ManageInvites(View):
    """create invites"""

    def get(self, request):
        """invite management page"""
        paginated = Paginator(
            models.SiteInvite.objects.filter(user=request.user).order_by(
                "-created_date"
            ),
            PAGE_LENGTH,
        )

        page = paginated.get_page(request.GET.get("page"))
        data = {
            "invites": page,
            "page_range": paginated.get_elided_page_range(
                page.number, on_each_side=2, on_ends=1
            ),
            "form": forms.CreateInviteForm(),
        }
        return TemplateResponse(request, "settings/manage_invites.html", data)

    def post(self, request):
        """creates an invite database entry"""
        form = forms.CreateInviteForm(request.POST)
        if not form.is_valid():
            return HttpResponseBadRequest("ERRORS : %s" % (form.errors,))

        invite = form.save(commit=False)
        invite.user = request.user
        invite.save()

        paginated = Paginator(
            models.SiteInvite.objects.filter(user=request.user).order_by(
                "-created_date"
            ),
            PAGE_LENGTH,
        )
        data = {"invites": paginated.page(1), "form": form}
        return TemplateResponse(request, "settings/manage_invites.html", data)


class Invite(View):
    """use an invite to register"""

    def get(self, request, code):
        """endpoint for using an invites"""
        if request.user.is_authenticated:
            return redirect("/")
        invite = get_object_or_404(models.SiteInvite, code=code)

        data = {
            "register_form": forms.RegisterForm(),
            "invite": invite,
            "valid": invite.valid() if invite else True,
        }
        return TemplateResponse(request, "invite.html", data)

    # post handling is in views.authentication.Register


class ManageInviteRequests(View):
    """grant invites like the benevolent lord you are"""

    def get(self, request):
        """view a list of requests"""
        ignored = request.GET.get("ignored", False)
        sort = request.GET.get("sort")
        sort_fields = [
            "created_date",
            "invite__times_used",
            "invite__invitees__created_date",
        ]
        if not sort in sort_fields + ["-{:s}".format(f) for f in sort_fields]:
            sort = "-created_date"

        requests = models.InviteRequest.objects.filter(ignored=ignored).order_by(sort)

        status_filters = [
            s
            for s in request.GET.getlist("status")
            if s in ["requested", "sent", "accepted"]
        ]

        filters = []
        if "requested" in status_filters:
            filters.append({"invite__isnull": True})
        if "sent" in status_filters:
            filters.append({"invite__isnull": False, "invite__times_used": 0})
        if "accepted" in status_filters:
            filters.append({"invite__isnull": False, "invite__times_used__gte": 1})

        if filters:
            requests = requests.filter(
                reduce(operator.or_, (Q(**f) for f in filters))
            ).distinct()

        paginated = Paginator(requests, PAGE_LENGTH)

        page = paginated.get_page(request.GET.get("page"))
        data = {
            "ignored": ignored,
            "count": paginated.count,
            "requests": page,
            "page_range": paginated.get_elided_page_range(
                page.number, on_each_side=2, on_ends=1
            ),
            "sort": sort,
        }
        return TemplateResponse(request, "settings/manage_invite_requests.html", data)

    def post(self, request):
        """send out an invite"""
        invite_request = get_object_or_404(
            models.InviteRequest, id=request.POST.get("invite-request")
        )
        # only create a new invite if one doesn't exist already (resending)
        if not invite_request.invite:
            invite_request.invite = models.SiteInvite.objects.create(
                use_limit=1,
                user=request.user,
            )
            invite_request.save()
        emailing.invite_email(invite_request)
        return redirect(
            "{:s}?{:s}".format(
                reverse("settings-invite-requests"), urlencode(request.GET.dict())
            )
        )


class InviteRequest(View):
    """prospective users sign up here"""

    def post(self, request):
        """create a request"""
        form = forms.InviteRequestForm(request.POST)
        received = False
        if form.is_valid():
            received = True
            form.save()

        data = {
            "request_form": form,
            "request_received": received,
            "books": helpers.get_discover_books(),
        }
        return TemplateResponse(request, "discover/discover.html", data)


@require_POST
def ignore_invite_request(request):
    """hide an invite request"""
    invite_request = get_object_or_404(
        models.InviteRequest, id=request.POST.get("invite-request")
    )

    invite_request.ignored = not invite_request.ignored
    invite_request.save()
    return redirect("settings-invite-requests")
