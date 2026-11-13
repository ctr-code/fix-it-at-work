"""{{ text|ticket_links }}: a message to a reporter with each ticket number linked to its track page."""
import re

from django import template
from django.urls import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

TICKET = re.compile(r'\bTKT-\d{4}-\d{4,}\b')


@register.filter
def ticket_links(text):
    return mark_safe(TICKET.sub(lambda m: f'<a href="{reverse("track_case", args=[m.group(0)])}">{m.group(0)}</a>',
                                escape(text or '')))
