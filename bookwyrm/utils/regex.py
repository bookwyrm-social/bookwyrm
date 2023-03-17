""" defining regexes for regularly used concepts """

DOMAIN = r"[\w_\-\.]+\.[a-z\-]{2,}"
LOCALNAME = r"@?[a-zA-Z_\-\.0-9]+"
STRICT_LOCALNAME = r"@[a-zA-Z_\-\.0-9]+"
USERNAME = rf"{LOCALNAME}(@{DOMAIN})?"
STRICT_USERNAME = rf"(\B{STRICT_LOCALNAME}(@{DOMAIN})?\b)"
FULL_USERNAME = rf"{LOCALNAME}@{DOMAIN}\b"
SLUG = r"/s/(?P<slug>[-_a-z0-9]*)"
HASHTAG = r"(#[^!@#$%^&*(),.?\":{}|<>\s]+)"
# should match (BookWyrm/1.0.0; or (BookWyrm/99.1.2;
BOOKWYRM_USER_AGENT = r"\(BookWyrm/[0-9]+\.[0-9]+\.[0-9]+;"
