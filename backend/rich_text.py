"""Sanitize supported résumé formatting and distinguish it from legacy text."""

from html.parser import HTMLParser
import unicodedata
import nh3
from markupsafe import Markup, escape

TEXT_LIMIT = 20000
HTML_LIMIT = 100000
TAGS = {'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'h1', 'h2', 'h3', 'ul', 'ol', 'li', 'span'}
SIZE_CLASSES = {'ql-size-small', 'ql-size-large', 'ql-size-huge'}


class TextContent(HTMLParser):
    """Collect text for empty-content and visible-length validation."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def sanitize_html(value):
    """Keep structural formatting and preset Quill size classes only."""
    return nh3.clean(value, tags=TAGS, attributes={},
                     allowed_classes={'span': SIZE_CLASSES},
                     clean_content_tags={'script', 'style', 'iframe', 'object', 'svg', 'math', 'template'},
                     link_rel=None)


def prepare_content(value, content_format):
    """Validate format/size and return a safe storage representation."""
    if content_format not in ('plain', 'html'):
        raise ValueError('Unsupported résumé format.')
    if content_format == 'plain':
        if not value.strip() or len(value) > TEXT_LIMIT:
            raise ValueError('Enter resume text with 1 to 20,000 characters.')
        return value
    if len(value) > HTML_LIMIT:
        raise ValueError('Formatted résumé is too large.')
    cleaned = sanitize_html(value)
    parser = TextContent()
    parser.feed(cleaned)
    text = ''.join(parser.parts)
    meaningful = ''.join(c for c in text if not c.isspace() and not unicodedata.category(c).startswith('C'))
    if not meaningful or len(text) > TEXT_LIMIT or len(cleaned) > HTML_LIMIT:
        raise ValueError('Enter resume text with 1 to 20,000 characters.')
    return cleaned


def render_content(value, content_format):
    """Mark only sanitized HTML safe; plain text always remains escaped."""
    return Markup(sanitize_html(value)) if content_format == 'html' else escape(value)
