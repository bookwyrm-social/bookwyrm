# Generated by Django 3.2.18 on 2023-05-16 16:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookwyrm", "0178_auto_20230328_2132"),
    ]

    operations = [
        migrations.AddField(
            model_name="reportcomment",
            name="action_type",
            field=models.CharField(
                choices=[
                    ("comment", "Comment"),
                    ("resolve", "Resolved report"),
                    ("reopen", "Re-opened report"),
                    ("message_reporter", "Messaged reporter"),
                    ("message_offender", "Messaged reported user"),
                    ("user_suspension", "Suspended user"),
                    ("user_unsuspension", "Un-suspended user"),
                    ("user_perms", "Changed user permission level"),
                    ("user_deletion", "Deleted user account"),
                    ("block_domain", "Blocked domain"),
                    ("approve_domain", "Approved domain"),
                    ("delete_item", "Deleted item"),
                ],
                default="comment",
                max_length=20,
            ),
        ),
        migrations.RenameModel("ReportComment", "ReportAction"),
    ]