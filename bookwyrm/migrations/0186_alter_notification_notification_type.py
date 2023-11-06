# Generated by Django 3.2.20 on 2023-11-05 14:55

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bookwyrm", "0185_merge_20231105_1453"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="notification_type",
            field=models.CharField(
                choices=[
                    ("FAVORITE", "Favorite"),
                    ("REPLY", "Reply"),
                    ("MENTION", "Mention"),
                    ("TAG", "Tag"),
                    ("FOLLOW", "Follow"),
                    ("FOLLOW_REQUEST", "Follow Request"),
                    ("BOOST", "Boost"),
                    ("IMPORT", "Import"),
                    ("USER_IMPORT", "User Import"),
                    ("USER_EXPORT", "User Export"),
                    ("ADD", "Add"),
                    ("REPORT", "Report"),
                    ("LINK_DOMAIN", "Link Domain"),
                    ("INVITE", "Invite"),
                    ("ACCEPT", "Accept"),
                    ("JOIN", "Join"),
                    ("LEAVE", "Leave"),
                    ("REMOVE", "Remove"),
                    ("GROUP_PRIVACY", "Group Privacy"),
                    ("GROUP_NAME", "Group Name"),
                    ("GROUP_DESCRIPTION", "Group Description"),
                    ("MOVE", "Move"),
                ],
                max_length=255,
            ),
        ),
    ]