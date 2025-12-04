# Generated manually for daily newsletter subscription preference

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookwyrm", "0223_user_show_inactive_suggestions"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="newsletter_subscription",
            field=models.BooleanField(default=False),
        ),
    ]
