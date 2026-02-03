"""Database utilities"""

from typing import Optional, Iterable, Set, cast
import sqlparse  # type: ignore[import-untyped]


def format_trigger(sql: str) -> str:
    """format SQL trigger before storing

    we remove whitespace and use consistent casing so as to avoid migrations
    due to formatting changes.
    """
    return cast(
        str,
        sqlparse.format(
            sql,
            strip_comments=True,
            strip_whitespace=True,
            use_space_around_operators=True,
            keyword_case="upper",
            identifier_case="lower",
        ),
    )


def add_update_fields(
    update_fields: Optional[Iterable[str]], *fields: str
) -> Optional[Set[str]]:
    """
    Helper for adding fields to the update_fields kwarg when modifying an object
    in a model's save() method.

    https://docs.djangoproject.com/en/5.0/releases/4.2/#setting-update-fields-in-model-save-may-now-be-required
    """
    return set(fields).union(update_fields) if update_fields is not None else None
