''' send emails '''
from django.core.mail import send_mail

from bookwyrm import models
from bookwyrm.tasks import app

def password_reset_email(reset_code):
    ''' generate a password reset email '''
    site = models.SiteSettings.get()
    send_email.delay(
        reset_code.user.email,
        'Reset your password on %s' % site.name,
        'Your password reset link: %s' % reset_code.link
    )

@app.task
def send_email(recipient, subject, message):
    ''' use a task to send the email '''
    send_mail(
        subject,
        message,
        None, # sender will be the config default
        [recipient],
        fail_silently=False
    )
