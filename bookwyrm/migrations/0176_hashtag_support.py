# Generated by Django 3.2.16 on 2022-12-17 19:28

import bookwyrm.models.fields
import django.contrib.postgres.fields.citext
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookwyrm", "0174_auto_20230130_1240"),
    ]

    operations = [
        migrations.CreateModel(
            name="Hashtag",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_date", models.DateTimeField(auto_now_add=True)),
                ("updated_date", models.DateTimeField(auto_now=True)),
                (
                    "remote_id",
                    bookwyrm.models.fields.RemoteIdField(
                        max_length=255,
                        null=True,
                        validators=[bookwyrm.models.fields.validate_remote_id],
                    ),
                ),
                (
                    "name",
                    django.contrib.postgres.fields.citext.CICharField(max_length=256),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.AddField(
            model_name="status",
            name="mention_hashtags",
            field=bookwyrm.models.fields.TagField(
                related_name="mention_hashtag", to="bookwyrm.Hashtag"
            ),
        ),
    ]