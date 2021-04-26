""" send emails """
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template

from bookwyrm import models, settings
from bookwyrm.tasks import app
from bookwyrm.settings import DOMAIN


def email_data():
    """fields every email needs"""
    site = models.SiteSettings.objects.get()
    if site.logo_small:
        logo_path = "/images/{}".format(site.logo_small.url)
    else:
        logo_path = "/static/images/logo-small.png"

    return {
        "site_name": site.name,
        "logo": logo_path,
        "domain": DOMAIN,
        "user": None,
    }


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
    send_email.delay(reset_code.user.email, *format_email("password_reset", data))


def format_email(email_name, data):
    """render the email templates"""
    subject = (
        get_template("email/{}/subject.html".format(email_name)).render(data).strip()
    )
    html_content = (
        get_template("email/{}/html_content.html".format(email_name))
        .render(data)
        .strip()
    )
    text_content = (
        get_template("email/{}/text_content.html".format(email_name))
        .render(data)
        .strip()
    )
    return (subject, html_content, text_content)


@app.task
def send_email(recipient, subject, html_content, text_content):
    """use a task to send the email"""
    email = EmailMultiAlternatives(
        subject, text_content, settings.DEFAULT_FROM_EMAIL, [recipient]
    )
    email.attach_alternative(html_content, "text/html")
    email.send()
