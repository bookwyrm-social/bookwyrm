# Generated manually for connector health tracking

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookwyrm", "0221_user_force_password_reset"),
    ]

    operations = [
        migrations.AddField(
            model_name="connector",
            name="health_status",
            field=models.CharField(
                choices=[
                    ("healthy", "Healthy"),
                    ("degraded", "Degraded"),
                    ("unavailable", "Unavailable"),
                ],
                default="healthy",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="connector",
            name="last_success_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="connector",
            name="last_failure_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="connector",
            name="failure_count",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="connector",
            name="success_count",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="connector",
            name="avg_response_ms",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
