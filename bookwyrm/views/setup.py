""" Installation wizard 🧙 """
from django.contrib.auth import login
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.views import View

from bookwyrm import forms, models
from bookwyrm.settings import DOMAIN


# pylint: disable= no-self-use
class CreateAdmin(View):
    """manage things like the instance name"""

    def get(self, request):
        """Create admin user form"""
        # only allow this view when an instance is being configured
        site = models.SiteSettings.objects.get()
        if not site.install_mode:
            raise PermissionDenied()

        data = {
            "register_form": forms.RegisterForm()
        }
        return TemplateResponse(request, "setup/admin.html", data)

    @transaction.atomic
    def post(self, request):
        """Create that user"""
        site = models.SiteSettings.get()
        # you can't create an admin user if you're in config mode
        if not site.install_mode:
            raise PermissionDenied()

        form = forms.RegisterForm(request.POST)
        if not form.is_valid():
            data = {"register_form": form}
            return TemplateResponse(request, "setup/admin.html", data)

        localname = form.data["localname"].strip()
        username = f"{localname}@{DOMAIN}"

        user = models.User.objects.create_superuser(
            username,
            form.data["email"],
            form.data["password"],
            localname=localname,
            local=True,
            deactivation_reason=None,
            is_active=True,
        )
        # Set "admin" role
        try:
            user.groups.set(Group.objects.filter(name__in=["admin", "moderator"]))
        except Group.DoesNotExist:
            # this should only happen in tests
            pass

        login(request, user)
        site.install_mode = False
        site.save()
        return redirect("settings-site")
