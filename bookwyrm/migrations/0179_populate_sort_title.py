import re
from itertools import chain

from django.db import migrations, transaction
from django.db.models import Q

from bookwyrm.settings import LANGUAGE_ARTICLES


@transaction.atomic
def populate_sort_title(apps, schema_editor):
    Edition = apps.get_model("bookwyrm", "Edition")
    db_alias = schema_editor.connection.alias
    editions_wo_sort_title = Edition.objects.using(db_alias).filter(
        Q(sort_title__isnull=True) | Q(sort_title__exact="")
    )
    for edition in editions_wo_sort_title:
        articles = chain(
            *(LANGUAGE_ARTICLES.get(language, ()) for language in edition.languages)
        )
        if articles:
            icase_articles = (
                f"[{a[0].capitalize()}{a[0].lower()}]{a[1:]}" for a in articles
            )
            edition.sort_title = re.sub(
                f'^{" |^".join(icase_articles)} ', "", edition.title
            )
        else:
            edition.sort_title = edition.title
        edition.save()


class Migration(migrations.Migration):

    dependencies = [
        ("bookwyrm", "0178_auto_20230328_2132"),
    ]

    operations = [
        migrations.RunPython(populate_sort_title),
    ]
