"""Clean user-provided text"""
import bleach


def clean(input_text: str) -> str:
    """Run through "bleach" """
    return bleach.clean(
        input_text,
        tags=[
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
        ],
        attributes=["href", "rel", "src", "alt", "data-mention"],
        strip=True,
    )
