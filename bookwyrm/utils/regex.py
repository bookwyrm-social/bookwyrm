''' defining regexes for regularly used concepts '''

domain = r'[a-z-A-Z0-9_\-]+\.[a-z]+'
localname = r'@?[a-zA-Z_\-\.0-9]+'
strict_localname = r'@[a-zA-Z_\-\.0-9]+'
username = r'%s(@%s)?' % (localname, domain)
strict_username = r'%s(@%s)?' % (strict_localname, domain)
full_username = r'%s@%s' % (localname, domain)
# should match (BookWyrm/1.0.0; or (BookWyrm/99.1.2;
bookwyrm_user_agent = r'\(BookWyrm/[0-9]+\.[0-9]+\.[0-9]+;'
