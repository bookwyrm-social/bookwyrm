"""Clean user-provided text"""

import bleach


def clean(input_text: str) -> str:
    """Run through "bleach" """
    return bleach.clean(
        input_text,
        tags={
            "p",
            "blockquote",
            "br",
            "b",
            "i",
            "strong",
            "em",
            "pre",
            "a",
            "span",
            "ul",
            "ol",
            "li",
            "img",
        },
        attributes=["href", "rel", "sizes", "src", "srcset", "alt", "data-mention"],
        strip=True,
    )
