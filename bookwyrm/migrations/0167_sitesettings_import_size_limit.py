# Generated by Django 3.2.16 on 2022-12-05 13:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookwyrm", "0166_sitesettings_imports_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="import_size_limit",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="import_limit_reset",
            field=models.IntegerField(default=0),
        ),
    ]
