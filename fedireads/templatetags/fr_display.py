''' template filters '''
from django import template

register = template.Library()

@register.filter(name='dict_key')
def dict_key(d, k):
    '''Returns the given key from a dictionary.'''
    return d.get(k) or 0

@register.filter(name='stars')
def stars(number):
    ''' turn integers into stars '''
    try:
        number = int(number)
    except TypeError:
        number = 0
    return ('★' * number) + '☆' * (5 - number)

@register.filter(name='description')
def description_format(description):
    ''' handle the various OL description formats '''
    if isinstance(description, dict) and 'value' in description:
        description = description['value']
    if '----------' in description:
        description = description.split('----------')[0]

    return description.strip()

@register.filter(name='author_bio')
def bio_format(bio):
    ''' clean up OL author bios '''
    bio = bio.split('\n')
    return bio[0].strip()
