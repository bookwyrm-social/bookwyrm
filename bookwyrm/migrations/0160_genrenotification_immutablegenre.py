# Generated by Django 3.2.15 on 2022-09-04 05:10

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


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
        migrations.CreateModel(
            name='GenreNotification',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(default=django.utils.timezone.now)),
                ('unread', models.BooleanField(default=True)),
                ('book', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='bookwyrm.book')),
                ('from_genre', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notification_from', to='bookwyrm.genre')),
                ('to_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notification_to', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-created',),
                'index_together': {('to_user', 'unread')},
            },
        ),
    ]