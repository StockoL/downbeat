from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def recording(path, seconds=None):
    """
    A recording as the teacher can reach it: a link straight to the moment when it's a web address
    (a media fragment, #t=102), otherwise the path to open from the folder, with the moment beside it.
    """
    if not path:
        return ""
    at = f"{seconds // 60}:{seconds % 60:02d}" if seconds is not None else ""
    if path.startswith(("http://", "https://")):
        href = f"{path}#t={seconds}" if seconds is not None else path
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>{}', href, path, f" at {at}" if at else "")
    return format_html("<code>{}</code>{}", path, f" at {at}" if at else "")
