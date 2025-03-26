# Generated by Django 4.2.15 on 2024-09-03 11:22

import bookwyrm.models.fields
import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("bookwyrm", "0209_user_show_ratings"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserRelationshipImport",
            fields=[
                (
                    "childjob_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="bookwyrm.childjob",
                    ),
                ),
                (
                    "relationship",
                    bookwyrm.models.fields.CharField(
                        choices=[("follow", "Follow"), ("block", "Block")],
                        max_length=10,
                        null=True,
                    ),
                ),
                (
                    "remote_id",
                    bookwyrm.models.fields.RemoteIdField(
                        max_length=255,
                        null=True,
                        validators=[bookwyrm.models.fields.validate_remote_id],
                    ),
                ),
                ("fail_reason", models.TextField(null=True)),
            ],
            options={
                "abstract": False,
            },
            bases=("bookwyrm.childjob",),
        ),
        migrations.RemoveField(
            model_name="bookwyrmexportjob",
            name="json_completed",
        ),
        migrations.AddField(
            model_name="bookwyrmimportjob",
            name="retry",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="bookwyrmimportjob",
            name="required",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=bookwyrm.models.fields.CharField(blank=True, max_length=50),
                blank=True,
                size=None,
            ),
        ),
        migrations.CreateModel(
            name="UserImportPost",
            fields=[
                (
                    "childjob_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="bookwyrm.childjob",
                    ),
                ),
                ("json", models.JSONField()),
                (
                    "status_type",
                    bookwyrm.models.fields.CharField(
                        choices=[
                            ("comment", "Comment"),
                            ("review", "Review"),
                            ("quote", "Quotation"),
                        ],
                        default="comment",
                        max_length=10,
                        null=True,
                    ),
                ),
                ("fail_reason", models.TextField(null=True)),
                (
                    "book",
                    bookwyrm.models.fields.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="bookwyrm.edition",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("bookwyrm.childjob",),
        ),
        migrations.CreateModel(
            name="UserImportBook",
            fields=[
                (
                    "childjob_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="bookwyrm.childjob",
                    ),
                ),
                ("book_data", models.JSONField()),
                ("fail_reason", models.TextField(null=True)),
                (
                    "book",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="bookwyrm.book",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("bookwyrm.childjob",),
        ),
    ]
