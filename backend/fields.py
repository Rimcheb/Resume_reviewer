"""Normalize supported role categories without changing original résumé text."""

from backend.models import FIELDS

ALIASES = {
    'swe': 'Software engineering', 'software engineer': 'Software engineering',
    'software developer': 'Software engineering', 'software': 'Software engineering',
    'data scientist': 'Data science', 'pm': 'Product management',
    'product manager': 'Product management', 'ux': 'Design (UX/UI)',
    'ui': 'Design (UX/UI)', 'ux/ui': 'Design (UX/UI)', 'design': 'Design (UX/UI)',
}
CANONICAL = {field.casefold(): field for field in FIELDS}


def normalize_field(value):
    """Return a category for known labels/aliases, or None for unknown labels.

    Common internship suffixes in legacy submissions are accepted explicitly.
    Unknown fields are not silently classified as Other.
    """
    if len(value) > 100:
        return None
    label = ' '.join(value.split()).casefold()
    for suffix in (' internship', ' intern'):
        if label.endswith(suffix):
            label = label[:-len(suffix)].strip()
            break
    return CANONICAL.get(label) or ALIASES.get(label)
