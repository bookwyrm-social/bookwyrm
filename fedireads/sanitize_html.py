''' html parser to clean up incoming text from unknown sources '''
from html.parser import HTMLParser

class InputHtmlParser(HTMLParser):
    ''' Removes any html that isn't whitelisted from a block '''

    def __init__(self):
        HTMLParser.__init__(self)
        self.whitelist = ['p', 'b', 'i', 'pre']
        self.tag_stack = []
        self.output = []
        # if the html appears invalid, we just won't allow any at all
        self.allow_html = True


    def handle_starttag(self, tag, attrs):
        ''' check if the tag is valid '''
        if self.allow_html and tag in self.whitelist:
            self.output.append(('tag', '<%s>' % tag))
            self.tag_stack.append(tag)
        else:
            self.output.append(('data', ' '))


    def handle_endtag(self, tag):
        ''' keep the close tag '''
        if not self.allow_html or tag not in self.whitelist:
            self.output.append(('data', ' '))
            return

        if not self.tag_stack or self.tag_stack[-1] != tag:
            # the end tag doesn't match the most recent start tag
            self.allow_html = False
            self.output.append(('data', ' '))
            return

        self.tag_stack = self.tag_stack[:-1]
        self.output.append(('tag', '</%s>' % tag))


    def handle_data(self, data):
        ''' extract the answer, if we're in an answer tag '''
        self.output.append(('data', data))


    def get_output(self):
        ''' convert the output from a list of tuples to a string '''
        if not self.allow_html:
            return ''.join(v for (k, v) in self.output if k == 'data')
        return ''.join(v for (k, v) in self.output)

