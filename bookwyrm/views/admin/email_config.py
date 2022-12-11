""" is your email running? """
from django.contrib.auth.decorators import login_required, permission_required
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import emailing
from bookwyrm import settings

# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_instance_settings", raise_exception=True),
    name="dispatch",
)
class EmailConfig(View):
    """View and test your emailing setup"""

    def get(self, request):
        """View email config"""
        data = view_data()
        # TODO: show email previews
        return TemplateResponse(request, "settings/email_config.html", data)

    def post(self, request):
        """Send test email"""
        data = view_data()
        try:
            emailing.test_email(request.user)
            data["success"] = True
        except Exception as err:  # pylint: disable=broad-except
            data["error"] = err
        return TemplateResponse(request, "settings/email_config.html", data)


def view_data():
    """helper to get data for view"""
    return {
        "email_backend": settings.EMAIL_BACKEND,
        "email_host": settings.EMAIL_HOST,
        "email_port": settings.EMAIL_PORT,
        "Email_host_user": settings.EMAIL_HOST_USER,
        "email_use_tls": settings.EMAIL_USE_TLS,
        "email_use_ssl": settings.EMAIL_USE_SSL,
        "email_sender": settings.EMAIL_SENDER,
    }


@login_required
@permission_required("bookwyrm.edit_instance_settings", raise_exception=True)
def email_preview(request):
    """for development, renders and example email template"""
    template = request.GET.get("email")
    data = emailing.email_data()
    data["subject_path"] = f"email/{template}/subject.html"
    data["html_content_path"] = f"email/{template}/html_content.html"
    data["text_content_path"] = f"email/{template}/text_content.html"
    data["reset_link"] = "https://example.com/link"
    data["invite_link"] = "https://example.com/link"
    data["confirmation_link"] = "https://example.com/link"
    data["confirmation_code"] = "AKJHKDGKJSDFG"
    data["reporter"] = "ConcernedUser"
    data["reportee"] = "UserName"
    data["report_link"] = "https://example.com/link"
    return TemplateResponse(request, "email/preview.html", data)
