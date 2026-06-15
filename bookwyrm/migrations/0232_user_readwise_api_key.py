"""add Readwise integration token"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bookwyrm", "0231_sitesettings_block_incoming_search_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="readwise_api_key",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
