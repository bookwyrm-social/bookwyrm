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
    number = int(number)
    return ('★' * number) + '☆' * (5 - number)
