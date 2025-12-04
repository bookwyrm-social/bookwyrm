# Generated manually for suggestion filtering preference

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookwyrm", "0222_connector_health_tracking"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="show_inactive_suggestions",
            field=models.BooleanField(default=True),
        ),
    ]
