from django.db import migrations


def forwards_func(apps, schema_editor):
    # Set all values for ListItem.order
    BookList = apps.get_model("bookwyrm", "List")
    db_alias = schema_editor.connection.alias
    for book_list in BookList.objects.using(db_alias).all():
        for i, item in enumerate(book_list.listitem_set.order_by("id"), 1):
            item.order = i
            item.save()


def reverse_func(apps, schema_editor):
    # null all values for ListItem.order
    BookList = apps.get_model("bookwyrm", "List")
    db_alias = schema_editor.connection.alias
    for book_list in BookList.objects.using(db_alias).all():
        for item in book_list.listitem_set.order_by("id"):
            item.order = None
            item.save()


class Migration(migrations.Migration):

    dependencies = [
        ("bookwyrm", "0066_user_deactivation_reason"),
    ]

    operations = [migrations.RunPython(forwards_func, reverse_func)]
