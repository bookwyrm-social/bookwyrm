''' defining regexes for regularly used concepts '''

domain = r'[a-z-A-Z0-9_\-]+\.[a-z]+'
username = r'@[a-zA-Z_\-\.0-9]+(@%s)?' % domain
full_username = r'@?[a-zA-Z_\-\.0-9]+@%s' % domain
