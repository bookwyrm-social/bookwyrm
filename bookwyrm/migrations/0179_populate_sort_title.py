import re
from itertools import chain

from django.db import migrations, transaction
from django.db.models import Q

from bookwyrm.settings import LANGUAGE_ARTICLES


def set_sort_title(edition):
    articles = chain(
        *(LANGUAGE_ARTICLES.get(language, ()) for language in tuple(edition.languages))
    )
    edition.sort_title = re.sub(
        f'^{" |^".join(articles)} ', "", str(edition.title).lower()
    )
    return edition


@transaction.atomic
def populate_sort_title(apps, schema_editor):
    Edition = apps.get_model("bookwyrm", "Edition")
    db_alias = schema_editor.connection.alias
    editions_wo_sort_title = Edition.objects.using(db_alias).filter(
        Q(sort_title__isnull=True) | Q(sort_title__exact="")
    )
    batch_size = 1000
    start = 0
    end = batch_size
    while True:
        batch = editions_wo_sort_title[start:end]
        if not batch.exists():
            break
        Edition.objects.bulk_update(
            (set_sort_title(edition) for edition in batch), ["sort_title"]
        )
        start = end
        end += batch_size


class Migration(migrations.Migration):

    dependencies = [
        ("bookwyrm", "0178_auto_20230328_2132"),
    ]

    operations = [
        migrations.RunPython(populate_sort_title),
    ]
