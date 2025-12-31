"""
Custom template tags for scheduling app
"""
from django import template

register = template.Library()


@register.filter
def lookup(dictionary, key):
    """
    Dictionary lookup filter
    Usage: {{ mydict|lookup:key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key, None)


@register.filter
def get_item(dictionary, key):
    """
    Alternative dictionary lookup
    Usage: {{ mydict|get_item:key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key, None)
