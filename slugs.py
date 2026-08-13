import re
import unicodedata

_NON_ALNUM = re.compile(r'[^a-z0-9]+')


def slugify(value):
    """Turn a display name into a URL slug.

    'Beauty & Personal Care' -> 'beauty-personal-care'
    """
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = text.encode('ascii', 'ignore').decode('ascii').lower()
    text = _NON_ALNUM.sub('-', text).strip('-')
    return text or 'item'
