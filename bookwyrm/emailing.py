""" send emails """
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template

from bookwyrm import models, settings
from bookwyrm.tasks import app, EMAIL
from bookwyrm.settings import DOMAIN, BASE_URL


def email_data():
    """fields every email needs"""
    site = models.SiteSettings.objects.get()
    return {
        "site_name": site.name,
        "logo": site.logo_small_url,
        "domain": DOMAIN,
        "base_url": BASE_URL,
        "user": None,
    }


def test_email(user):
    """Just an admin checking if emails are sending"""
    data = email_data()
    send_email(user.email, *format_email("test", data))


def email_confirmation_email(user):
    """newly registered users confirm email address"""
    data = email_data()
    data["confirmation_code"] = user.confirmation_code
    data["confirmation_link"] = user.confirmation_link
    send_email(user.email, *format_email("confirm", data))


def invite_email(invite_request):
    """send out an invite code"""
    data = email_data()
    data["invite_link"] = invite_request.invite.link
    send_email.delay(invite_request.email, *format_email("invite", data))


def password_reset_email(reset_code):
    """generate a password reset email"""
    data = email_data()
    data["reset_link"] = reset_code.link
    data["user"] = reset_code.user.display_name
    send_email(reset_code.user.email, *format_email("password_reset", data))


def moderation_report_email(report):
    """a report was created"""
    data = email_data()
    data["reporter"] = report.user.localname or report.user.username
    if report.reported_user:
        data["reportee"] = (
            report.reported_user.localname or report.reported_user.username
        )
    data["report_link"] = report.remote_id
    data["link_domain"] = report.links.exists()

    for admin in models.User.objects.filter(
        groups__name__in=["admin", "moderator"]
    ).distinct():
        data["user"] = admin.display_name
        send_email.delay(admin.email, *format_email("moderation_report", data))


def format_email(email_name, data):
    """render the email templates"""
    subject = get_template(f"email/{email_name}/subject.html").render(data).strip()
    html_content = (
        get_template(f"email/{email_name}/html_content.html").render(data).strip()
    )
    text_content = (
        get_template(f"email/{email_name}/text_content.html").render(data).strip()
    )
    return (subject, html_content, text_content)


@app.task(queue=EMAIL)
def send_email(recipient, subject, html_content, text_content):
    """use a task to send the email"""
    email = EmailMultiAlternatives(
        subject, text_content, settings.EMAIL_SENDER, [recipient]
    )
    email.attach_alternative(html_content, "text/html")
    email.send()
