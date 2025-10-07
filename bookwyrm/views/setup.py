""" Installation wizard 🧙 """
import re

from django.contrib.auth import login
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.views import View

from bookwyrm.activitypub import get_representative
from bookwyrm import forms, models
from bookwyrm import settings
from bookwyrm.utils import regex


# pylint: disable= no-self-use
class InstanceConfig(View):
    """make sure the instance looks correct before adding any data"""

    def get(self, request):
        """Check out this cool instance"""
        # only allow this view when an instance is being configured
        site = models.SiteSettings.objects.get()
        if not site.install_mode:
            raise PermissionDenied()

        # check for possible problems with the instance configuration
        warnings = {}
        warnings["debug"] = settings.DEBUG
        warnings["invalid_domain"] = not (
            re.match(rf"^{regex.DOMAIN}$", settings.DOMAIN)
            or (settings.DOMAIN == "localhost")
        )
        warnings["localhost"] = settings.DOMAIN == "localhost"

        # pylint: disable=line-too-long
        data = {
            "warnings": warnings,
            "info": {
                "domain": settings.DOMAIN,
                "base_url": settings.BASE_URL,
                "version": settings.VERSION,
                "language": settings.LANGUAGE_CODE,
                "use_s3": settings.USE_S3,
                "email_sender": f"{settings.EMAIL_SENDER_NAME}@{settings.EMAIL_SENDER_DOMAIN}",
                "preview_images": settings.ENABLE_PREVIEW_IMAGES,
                "thumbnails": settings.ENABLE_THUMBNAIL_GENERATION,
            },
        }
        return TemplateResponse(request, "setup/config.html", data)


class CreateAdmin(View):
    """manage things like the instance name"""

    def get(self, request):
        """Create admin user form"""
        # only allow this view when an instance is being configured
        site = models.SiteSettings.objects.get()
        if not site.install_mode:
            raise PermissionDenied()

        data = {"register_form": forms.RegisterForm()}
        return TemplateResponse(request, "setup/admin.html", data)

    @transaction.atomic
    def post(self, request):
        """Create that user"""
        site = models.SiteSettings.objects.get()
        # you can't create an admin user if you're in config mode
        if not site.install_mode:
            raise PermissionDenied()

        form = forms.RegisterForm(request.POST)
        if not form.is_valid():
            data = {"register_form": form}
            return TemplateResponse(request, "setup/admin.html", data)

        localname = form.data["localname"].strip()
        username = f"{localname}@{settings.DOMAIN}"

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

        # record session
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            ip_address = forwarded_for.split(",")[0]
        else:
            ip_address = request.META.get("REMOTE_ADDR", "")
        agent_string = request.META.get("HTTP_USER_AGENT", "")
        models.create_user_session(
            user_id=user.id,
            session_key=request.session.session_key,
            ip_address=ip_address,
            agent_string=agent_string,
        )

        site.install_mode = False
        site.save()
        get_representative()  # create the instance user
        return redirect("settings-site")
