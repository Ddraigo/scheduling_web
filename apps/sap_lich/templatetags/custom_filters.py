from django import template

register = template.Library()


@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Custom template filter to get dictionary item by key
    Usage: {{ mydict|get_item:key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)
