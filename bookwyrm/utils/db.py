""" Database utilities """

from typing import cast
import sqlparse  # type: ignore


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
