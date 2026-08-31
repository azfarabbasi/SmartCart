"""In-memory caching service with TTL and explicit invalidation.

Provides ultra-fast, zero-roundtrip access to high-frequency, slow-changing
data such as Site Settings, Navigation Categories, Hero Banners, and Official Brands.
"""
import time
from slugs import slugify

_CACHE = {}
_CACHE_EXPIRY = {}
DEFAULT_TTL = 120  # 2 minutes TTL


def _get(key):
    if key in _CACHE:
        if time.time() < _CACHE_EXPIRY.get(key, 0):
            return _CACHE[key]
        else:
            _CACHE.pop(key, None)
            _CACHE_EXPIRY.pop(key, None)
    return None


def _set(key, value, ttl=DEFAULT_TTL):
    _CACHE[key] = value
    _CACHE_EXPIRY[key] = time.time() + ttl
    return value


def _invalidate(key_prefix):
    keys_to_del = [k for k in _CACHE if k.startswith(key_prefix)]
    for k in keys_to_del:
        _CACHE.pop(k, None)
        _CACHE_EXPIRY.pop(k, None)


def clear_all_caches():
    _CACHE.clear()
    _CACHE_EXPIRY.clear()


# ── 1. SITE SETTINGS ──────────────────────────────────────────────
def get_site_settings(cur=None):
    cached = _get('site_settings')
    if cached is not None:
        return cached

    import sitesettings
    values = dict(sitesettings.DEFAULTS)
    if cur is None:
        from db import get_db
        try:
            cur = get_db().cursor()
        except Exception:
            return values

    try:
        cur.execute("SELECT setting_key, setting_value FROM SiteSettings")
        for key, value in cur.fetchall():
            if value is not None:
                values[key] = value
        _set('site_settings', values, ttl=300)
    except Exception:
        pass
    return values


def invalidate_site_settings():
    _invalidate('site_settings')


# ── 2. CATEGORIES ────────────────────────────────────────────────
def get_all_categories(cur=None):
    cached = _get('all_categories')
    if cached is not None:
        return cached

    if cur is None:
        from db import get_db
        try:
            cur = get_db().cursor()
        except Exception:
            return []

    try:
        cur.execute("SELECT category_id, category_name FROM Categories ORDER BY category_name")
        rows = cur.fetchall()
        _set('all_categories', rows, ttl=180)
        return rows
    except Exception:
        return []


def get_nav_categories(cur=None):
    cached = _get('nav_categories')
    if cached is not None:
        return cached

    if cur is None:
        from db import get_db
        try:
            cur = get_db().cursor()
        except Exception:
            return []

    try:
        try:
            cur.execute(
                "SELECT category_id, category_name, icon_name, image_path, sort_order FROM ("
                "  SELECT category_id, category_name, icon_name, image_path, sort_order FROM Categories "
                "  ORDER BY NVL(sort_order, 0), category_name"
                ") WHERE ROWNUM <= 20"
            )
            rows = cur.fetchall()
            seen_names = set()
            nav_cats = []
            for row in rows:
                name_key = (row[1] or '').strip().lower()
                if name_key and name_key not in seen_names:
                    seen_names.add(name_key)
                    nav_cats.append({
                        'id': row[0],
                        'name': row[1],
                        'slug': slugify(row[1]),
                        'icon': row[2] or 'bi-tag',
                        'image': row[3],
                        'sort_order': row[4] or 0,
                    })
        except Exception:
            cur.execute(
                "SELECT category_name FROM ("
                "  SELECT DISTINCT category_name FROM Categories ORDER BY category_name"
                ") WHERE ROWNUM <= 20"
            )
            nav_cats = [
                {'name': row[0], 'slug': slugify(row[0]), 'icon': 'bi-tag', 'image': None, 'sort_order': 0}
                for row in cur.fetchall()
            ]
        _set('nav_categories', nav_cats, ttl=180)
        return nav_cats
    except Exception:
        return []


def invalidate_categories():
    _invalidate('all_categories')
    _invalidate('nav_categories')


# ── 3. HERO BANNERS ───────────────────────────────────────────────
def get_active_banners(cur=None):
    cached = _get('active_banners')
    if cached is not None:
        return cached

    if cur is None:
        from db import get_db
        try:
            cur = get_db().cursor()
        except Exception:
            return []

    try:
        cur.execute(
            "SELECT banner_id, badge_tag, title, subtitle, cta_text, cta_link, "
            "       gradient_class, image_path FROM HeroBanners "
            "WHERE is_active = 1 ORDER BY NVL(sort_order, 0), banner_id"
        )
        rows = cur.fetchall()
        _set('active_banners', rows, ttl=180)
        return rows
    except Exception:
        return []


def invalidate_banners():
    _invalidate('active_banners')


# ── 4. OFFICIAL BRANDS ────────────────────────────────────────────
def get_active_brands(cur=None):
    cached = _get('active_brands')
    if cached is not None:
        return cached

    if cur is None:
        from db import get_db
        try:
            cur = get_db().cursor()
        except Exception:
            return []

    try:
        cur.execute(
            "SELECT brand_id, brand_name, subtitle, logo_path, badge_text, badge_color, search_query "
            "FROM Brands WHERE is_active = 1 ORDER BY NVL(sort_order, 0), brand_name"
        )
        rows = cur.fetchall()
        _set('active_brands', rows, ttl=180)
        return rows
    except Exception:
        return []


def invalidate_brands():
    _invalidate('active_brands')
