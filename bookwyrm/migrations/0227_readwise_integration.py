# Generated manually for Readwise integration

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("bookwyrm", "0226_add_tufte_theme"),
    ]

    operations = [
        # Add Readwise fields to User model
        migrations.AddField(
            model_name="user",
            name="readwise_token",
            field=models.CharField(
                blank=True,
                help_text="Readwise API token for highlight sync",
                max_length=255,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="readwise_auto_export",
            field=models.BooleanField(
                default=False,
                help_text="Automatically export new quotes to Readwise",
            ),
        ),
        # Add Readwise field to Quotation model
        migrations.AddField(
            model_name="quotation",
            name="readwise_highlight_id",
            field=models.BigIntegerField(
                blank=True,
                help_text="Readwise highlight ID if exported to Readwise",
                null=True,
            ),
        ),
        # Create ReadwiseSync model
        migrations.CreateModel(
            name="ReadwiseSync",
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
                (
                    "last_export_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Last time quotes were exported to Readwise",
                        null=True,
                    ),
                ),
                (
                    "last_import_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Last time highlights were imported from Readwise",
                        null=True,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="readwise_sync",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Readwise Sync",
                "verbose_name_plural": "Readwise Syncs",
            },
        ),
        # Create ReadwiseSyncedHighlight model
        migrations.CreateModel(
            name="ReadwiseSyncedHighlight",
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
                (
                    "readwise_id",
                    models.BigIntegerField(
                        help_text="Highlight ID from Readwise API",
                    ),
                ),
                (
                    "readwise_book_id",
                    models.BigIntegerField(
                        blank=True,
                        help_text="Book ID from Readwise API (user_book_id)",
                        null=True,
                    ),
                ),
                (
                    "book_title",
                    models.CharField(
                        blank=True,
                        help_text="Book title from Readwise (for reference if no match)",
                        max_length=500,
                    ),
                ),
                (
                    "book_author",
                    models.CharField(
                        blank=True,
                        help_text="Book author from Readwise (for reference if no match)",
                        max_length=500,
                    ),
                ),
                (
                    "highlight_text",
                    models.TextField(
                        blank=True,
                        help_text="The highlight text (stored for debugging/reference)",
                    ),
                ),
                (
                    "imported_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="readwise_highlights",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "quotation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="readwise_source",
                        help_text="The BookWyrm quotation created from this highlight",
                        to="bookwyrm.quotation",
                    ),
                ),
                (
                    "matched_book",
                    models.ForeignKey(
                        blank=True,
                        help_text="The BookWyrm edition this was matched to",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="readwise_highlights",
                        to="bookwyrm.edition",
                    ),
                ),
            ],
            options={
                "verbose_name": "Readwise Synced Highlight",
                "verbose_name_plural": "Readwise Synced Highlights",
            },
        ),
        migrations.AddConstraint(
            model_name="readwisesyncedHighlight",
            constraint=models.UniqueConstraint(
                fields=["user", "readwise_id"],
                name="unique_user_readwise_highlight",
            ),
        ),
        migrations.AddIndex(
            model_name="readwisesyncedHighlight",
            index=models.Index(
                fields=["user", "readwise_book_id"],
                name="bookwyrm_re_user_id_readwise_idx",
            ),
        ),
    ]
