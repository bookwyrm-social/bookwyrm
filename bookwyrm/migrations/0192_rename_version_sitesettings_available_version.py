# Generated by Django 3.2.23 on 2024-01-02 19:36

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("bookwyrm", "0191_merge_20240102_0326"),
    ]

    operations = [
        migrations.RenameField(
            model_name="sitesettings",
            old_name="version",
            new_name="available_version",
        ),
    ]
