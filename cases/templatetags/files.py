"""{{ photo|private_url }}: the checked address of an uploaded file (see cases/files.py)."""
from django import template
from django.urls import reverse

register = template.Library()


@register.filter
def private_url(field_file):
    """The /files/ address for a stored photo or voice note, or '' if there's no file."""
    name = getattr(field_file, 'name', field_file)
    return reverse('case_file', args=[name]) if name else ''
