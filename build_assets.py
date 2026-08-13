"""Bundle every front-end asset into a single CSS and a single JS file.

The app used to pull Bootstrap, Bootstrap Icons and our own CSS/JS as five
separate requests, three of them from a third-party CDN. This produces:

    static/dist/app.css   bootstrap + (subset of) icons + our styles
    static/dist/app.js    bootstrap bundle + our scripts
    static/dist/fonts/    the icon webfont

Vercel serves `static/**` directly and never runs a build step, so the output
is committed to the repo. Re-run this script after editing static/css or
static/js:

    python build_assets.py
"""
import hashlib
import pathlib
import re
import sys
import urllib.request

BASE = pathlib.Path(__file__).resolve().parent
STATIC = BASE / 'static'
DIST = STATIC / 'dist'
CACHE = BASE / '.asset-cache'

BOOTSTRAP_VERSION = '5.3.2'
ICONS_VERSION = '1.11.1'
CHART_VERSION = '4.4.4'

SOURCES = {
    'bootstrap.css': f'https://cdn.jsdelivr.net/npm/bootstrap@{BOOTSTRAP_VERSION}/dist/css/bootstrap.min.css',
    'bootstrap.js': f'https://cdn.jsdelivr.net/npm/bootstrap@{BOOTSTRAP_VERSION}/dist/js/bootstrap.bundle.min.js',
    'icons.css': f'https://cdn.jsdelivr.net/npm/bootstrap-icons@{ICONS_VERSION}/font/bootstrap-icons.css',
    'icons.woff2': f'https://cdn.jsdelivr.net/npm/bootstrap-icons@{ICONS_VERSION}/font/fonts/bootstrap-icons.woff2',
    'chart.js': f'https://cdn.jsdelivr.net/npm/chart.js@{CHART_VERSION}/dist/chart.umd.min.js',
}

ICON_RULE = re.compile(r'^\.bi-([a-z0-9-]+)::before\s*\{')
# Matches an icon name anywhere it could be referenced -- `class="bi bi-cart4"`
# in a template, or `classList.add('bi-eye-slash')` in a script.
ICON_REFERENCE = re.compile(r'bi-([a-z0-9-]+)')


def fetch(name, url):
    """Download once, then reuse the cached copy on later builds."""
    CACHE.mkdir(exist_ok=True)
    cached = CACHE / name
    if not cached.exists():
        print(f'  downloading {name} ...')
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                cached.write_bytes(response.read())
        except Exception as exc:
            sys.exit(f'ERROR: could not download {url}\n  {exc}')
    return cached.read_bytes()


def used_icon_names():
    """Every bootstrap-icon name referenced by a template or script."""
    names = set()
    for folder, patterns in ((BASE / 'templates', ('*.html',)), (STATIC / 'js', ('*.js',))):
        for pattern in patterns:
            for path in folder.rglob(pattern):
                if DIST in path.parents:
                    continue
                names.update(ICON_REFERENCE.findall(path.read_text(encoding='utf-8')))
    return names


def subset_icons(css, wanted):
    """Drop the ~2000 icon rules we never render, keeping the shared setup."""
    kept, dropped = [], 0
    for line in css.splitlines():
        match = ICON_RULE.match(line)
        if match and match.group(1) not in wanted:
            dropped += 1
            continue
        kept.append(line)
    css = '\n'.join(kept)
    # Only woff2 ships (universally supported); point at our own copy of it.
    css = re.sub(
        r'src:\s*url\([^)]*\)\s*format\("woff2"\),\s*url\([^)]*\)\s*format\("woff"\);',
        'src: url("./fonts/bootstrap-icons.woff2") format("woff2");',
        css,
    )
    return css, dropped


def main():
    print('Bundling front-end assets')
    DIST.mkdir(parents=True, exist_ok=True)
    (DIST / 'fonts').mkdir(exist_ok=True)

    raw = {name: fetch(name, url) for name, url in SOURCES.items()}

    wanted = used_icon_names()
    icons_css, dropped = subset_icons(raw['icons.css'].decode('utf-8'), wanted)
    print(f'  icons: kept {len(wanted)} referenced, dropped {dropped} unused rules')

    app_css = '\n'.join([
        f'/* Bootstrap v{BOOTSTRAP_VERSION} | MIT | getbootstrap.com */',
        raw['bootstrap.css'].decode('utf-8'),
        f'/* Bootstrap Icons v{ICONS_VERSION} (subset) | MIT | icons.getbootstrap.com */',
        icons_css,
        '/* SmartCart styles */',
        (STATIC / 'css' / 'style.css').read_text(encoding='utf-8'),
    ])

    app_js = '\n'.join([
        f'/* Bootstrap v{BOOTSTRAP_VERSION} | MIT | getbootstrap.com */',
        raw['bootstrap.js'].decode('utf-8'),
        ';',
        '/* SmartCart scripts */',
        (STATIC / 'js' / 'script.js').read_text(encoding='utf-8'),
    ])

    # Chart.js is only needed by the admin analytics page, so it ships as its
    # own bundle instead of weighing down every other page load.
    analytics_js = '\n'.join([
        f'/* Chart.js v{CHART_VERSION} | MIT | chartjs.org */',
        raw['chart.js'].decode('utf-8'),
        ';',
        '/* SmartCart analytics */',
        (STATIC / 'js' / 'analytics.js').read_text(encoding='utf-8'),
    ])

    (DIST / 'app.css').write_text(app_css, encoding='utf-8')
    (DIST / 'app.js').write_text(app_js, encoding='utf-8')
    (DIST / 'analytics.js').write_text(analytics_js, encoding='utf-8')
    (DIST / 'fonts' / 'bootstrap-icons.woff2').write_bytes(raw['icons.woff2'])

    # Cache-busting stamp so a redeploy never serves a stale bundle.
    stamp = hashlib.sha256((app_css + app_js + analytics_js).encode('utf-8')).hexdigest()[:10]
    (DIST / 'version.txt').write_text(stamp, encoding='utf-8')

    for name in ('app.css', 'app.js', 'analytics.js'):
        print(f'  static/dist/{name}  {(DIST / name).stat().st_size / 1024:.0f} KB')
    print(f'  version {stamp}')


if __name__ == '__main__':
    main()
