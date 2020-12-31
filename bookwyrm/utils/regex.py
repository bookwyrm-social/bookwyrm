''' defining regexes for regularly used concepts '''

domain = r'[a-z-A-Z0-9_\-]+\.[a-z]+'
localname = r'@?[a-zA-Z_\-\.0-9]+'
username = r'%s(@%s)?' % (localname, domain)
full_username = r'%s@%s' % (localname, domain)
