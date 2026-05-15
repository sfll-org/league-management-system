"""Custom template filters for the core app."""

import json

from django import template

register = template.Library()


@register.filter(name='json_pretty')
def json_pretty(value):
    """Pretty-print a dict/list as indented JSON."""
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, default=str)
    try:
        parsed = json.loads(value)
        return json.dumps(parsed, indent=2, default=str)
    except (json.JSONDecodeError, TypeError):
        return str(value)
