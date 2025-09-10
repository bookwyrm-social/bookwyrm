""" defining regexes for regularly used concepts """

DOMAIN = r"[\w_\-\.]+\.[a-z\-]{2,}"
LOCALNAME = r"@?[a-zA-Z_\-\.0-9]+"
STRICT_LOCALNAME = r"@[a-zA-Z_\-\.0-9]+"
REMOTENAME = r"[\w\-\.\~](?:[\w\-\.\~]|(?:%[0-9A-Fa-f]{2})){0,149}"
USERNAME = rf"{LOCALNAME}(@{DOMAIN})?"
STRICT_USERNAME = rf"(\B{STRICT_LOCALNAME}(@{DOMAIN})?\b)"
FULL_USERNAME = rf"{LOCALNAME}@{DOMAIN}\b"
REMOTE_USER_URL = rf"(?:^http(?:s?):\/\/)([\w\-\.]*)(?:.)*(?:(?:\/)({REMOTENAME}))"
SLUG = r"/s/(?P<slug>[-_\w]*)"
HASHTAG = r"(#[^!@#$%^&*(),.?\":{}|<>\s]+)"
# should match (BookWyrm/1.0.0; or (BookWyrm/99.1.2;
BOOKWYRM_USER_AGENT = r"\(BookWyrm/[0-9]+\.[0-9]+\.[0-9]+;"
