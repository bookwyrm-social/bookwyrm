from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("bookwyrm", "0195_alter_user_preferred_language"),
    ]

    operations = [
        # join on bookwyrm_book_authors.author_id instead of .id
        migrations.RunSQL(
            sql="""
                CREATE OR REPLACE FUNCTION author_trigger() RETURNS trigger AS $$
                begin
                    WITH book AS (
                        SELECT bookwyrm_book.id as row_id
                        FROM bookwyrm_author
                        LEFT OUTER JOIN bookwyrm_book_authors
                        ON bookwyrm_book_authors.author_id = new.id
                        LEFT OUTER JOIN bookwyrm_book
                        ON bookwyrm_book.id = bookwyrm_book_authors.book_id
                    )
                    UPDATE bookwyrm_book SET search_vector = ''
                    FROM book
                    WHERE id = book.row_id;
                    return new;
                end
                $$ LANGUAGE plpgsql;

                UPDATE bookwyrm_book SET search_vector = NULL;
            """,
            reverse_sql="""
                CREATE OR REPLACE FUNCTION author_trigger() RETURNS trigger AS $$
                begin
                    WITH book AS (
                        SELECT bookwyrm_book.id as row_id
                        FROM bookwyrm_author
                        LEFT OUTER JOIN bookwyrm_book_authors
                        ON bookwyrm_book_authors.id = new.id
                        LEFT OUTER JOIN bookwyrm_book
                        ON bookwyrm_book.id = bookwyrm_book_authors.book_id
                    )
                    UPDATE bookwyrm_book SET search_vector = ''
                    FROM book
                    WHERE id = book.row_id;
                    return new;
                end
                $$ LANGUAGE plpgsql;
            """,
        ),
    ]
