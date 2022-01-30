# Generated by Django 3.2.10 on 2022-01-10 22:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookwyrm", "0126_filelink_link_linkdomain"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="report",
            name="self_report",
        ),
        migrations.AddField(
            model_name="report",
            name="links",
            field=models.ManyToManyField(blank=True, to="bookwyrm.Link"),
        ),
    ]
