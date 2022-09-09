# Generated by Django 3.2.15 on 2022-09-08 19:04

import bookwyrm.models.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bookwyrm', '0159_auto_20220825_0034'),
    ]

    operations = [
        migrations.CreateModel(
            name='ImmutableGenre',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('bookwyrm.genre',),
        ),
        migrations.AlterField(
            model_name='genre',
            name='description',
            field=bookwyrm.models.fields.CharField(max_length=500),
        ),
        migrations.AlterField(
            model_name='genre',
            name='genre_name',
            field=bookwyrm.models.fields.CharField(max_length=40),
        ),
    ]
