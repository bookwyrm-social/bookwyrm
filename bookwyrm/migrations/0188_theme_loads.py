# Generated by Django 3.2.23 on 2023-11-20 18:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookwyrm", "0187_partial_publication_dates"),
    ]

    operations = [
        migrations.AddField(
            model_name="theme",
            name="loads",
            field=models.BooleanField(blank=True, null=True),
        ),
    ]
