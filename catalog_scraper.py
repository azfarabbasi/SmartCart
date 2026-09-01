import base64
import json
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}


def normalize_url(url):
    """Ensure URL has scheme and clean domain."""
    if not url:
        return ''
    u = url.strip()
    if not u.startswith('http://') and not u.startswith('https://'):
        u = 'https://' + u
    return u.rstrip('/')


def verify_official_url(company_url):
    """Check if the provided company official website URL is reachable.
    
    Returns:
      (is_reachable, clean_url, site_name, error_msg)
    """
    clean = normalize_url(company_url)
    if not clean:
        return False, '', '', 'Please enter a valid website URL.'

    try:
        r = requests.get(clean, headers=HEADERS, timeout=10, allow_redirects=True)
        if r.status_code < 400:
            soup = BeautifulSoup(r.text, 'html.parser')
            site_title = soup.title.string.strip() if soup.title and soup.title.string else urllib.parse.urlparse(clean).netloc
            return True, clean, site_title, None
        return False, clean, '', f"Website returned status code {r.status_code}"
    except Exception as e:
        return False, clean, '', f"Could not connect to {clean}: {str(e)}"


def _decode_bing_url(href):
    """Decode redirect link from Bing search results."""
    m = re.search(r'[?&]u=a1([a-zA-Z0-9_-]+)', href)
    if m:
        b64 = m.group(1)
        b64 += '=' * ((4 - len(b64) % 4) % 4)
        try:
            return base64.urlsafe_b64decode(b64).decode('utf-8', errors='ignore')
        except Exception:
            pass
    return href


def _is_relevant_match(query, product_title_or_url):
    """Check if the found product title or URL has meaningful overlap with the searched product name."""
    if not query or not product_title_or_url:
        return False
    # Extract keywords >= 3 chars, ignoring common generic words
    stopwords = {'the', 'and', 'for', 'with', 'pro', 'new', 'official', 'product', 'buy', 'price', 'original'}
    words = re.findall(r'[a-zA-Z0-9]+', query.lower())
    keywords = [w for w in words if len(w) >= 2 and w not in stopwords]
    if not keywords:
        keywords = words

    target_text = str(product_title_or_url).lower().replace('-', ' ').replace('_', ' ')
    # If any specific model/keyword (e.g. 737, r950, r-950, soundcore) matches
    matched = [kw for kw in keywords if kw in target_text]
    # At least one meaningful token must match
    return len(matched) > 0


def search_product_on_official_website(company_url, product_name):
    """Search for a product specifically on the company's official website.
    
    If the product is NOT found on the official website, returns None
    (which enables automatic skipping).
    """
    if not company_url or not product_name:
        return None

    base_url = normalize_url(company_url)
    parsed_base = urllib.parse.urlparse(base_url)
    domain = parsed_base.netloc.lower().replace('www.', '')

    query = str(product_name).strip()
    query_clean = re.sub(r'[\(\)\[\]]', ' ', query).strip()

    # ── 1. Check Shopify native suggest / search endpoint ──────────────
    try:
        suggest_url = f"{base_url}/search/suggest.json?q={urllib.parse.quote(query_clean)}&resources[type]=product"
        r_suggest = requests.get(suggest_url, headers=HEADERS, timeout=6)
        if r_suggest.status_code == 200:
            data = r_suggest.json()
            products = data.get('resources', {}).get('results', {}).get('products', [])
            for p in products:
                prod_url = p.get('url', '')
                prod_title = p.get('title', '')
                if prod_url and _is_relevant_match(query_clean, prod_title or prod_url):
                    return urllib.parse.urljoin(base_url, prod_url)
    except Exception:
        pass

    # ── 2. Check Standard HTML Search on the site ─────────────────────
    search_paths = [
        f"/search?q={urllib.parse.quote(query_clean)}&type=product",
        f"/search?q={urllib.parse.quote(query_clean)}",
        f"/?s={urllib.parse.quote(query_clean)}&post_type=product",
    ]

    for path in search_paths:
        try:
            target = urllib.parse.urljoin(base_url, path)
            r = requests.get(target, headers=HEADERS, timeout=8)
            if r.status_code == 200:
                html_lower = r.text.lower()
                # Check for zero results message
                if any(nz in html_lower for nz in ['0 results', 'no results found', 'could not find any matches', 'no products were found']):
                    continue

                soup = BeautifulSoup(r.text, 'html.parser')

                # Prioritize search results container if available
                results_container = (
                    soup.select_one('.search-results, #product-grid, .grid--view-items, .main-search-results, .products.grid, .search__content')
                    or soup
                )

                for a in results_container.find_all('a', href=True):
                    href = a['href']
                    full_href = urllib.parse.urljoin(base_url, href)
                    link_text = a.get_text(' ', strip=True)

                    if domain in full_href and any(p in href.lower() for p in ['/products/', '/product/', '/item/', '/p/']):
                        if not any(x in href.lower() for x in ['/search', '/collections/', '/category/', 'sort_by']):
                            # Verify relevance to avoid matching recommendations/footer
                            if _is_relevant_match(query_clean, f"{link_text} {href}"):
                                return full_href
        except Exception:
            pass

    # ── 3. Site-scoped Search Fallback (site:{domain} {product_name}) ──
    try:
        bing_query = f"site:{domain} {query_clean}"
        bing_url = f"https://www.bing.com/search?q={urllib.parse.quote(bing_query)}"
        r_bing = requests.get(bing_url, headers=HEADERS, timeout=8)
        if r_bing.status_code == 200:
            soup = BeautifulSoup(r_bing.text, 'html.parser')
            for item in soup.select('li.b_algo h2 a')[:4]:
                raw_href = item.get('href', '')
                title_txt = item.get_text(' ', strip=True)
                decoded = _decode_bing_url(raw_href)
                parsed_decoded = urllib.parse.urlparse(decoded)
                if domain in parsed_decoded.netloc.lower():
                    path_lower = parsed_decoded.path.lower()
                    if path_lower not in ['', '/', '/privacy-policy', '/contact', '/about-us']:
                        if _is_relevant_match(query_clean, f"{title_txt} {path_lower}"):
                            return decoded
    except Exception:
        pass

    # If not found on official website, return None to trigger SKIP
    return None



def _download_image_as_data_url(img_url, max_bytes=2 * 1024 * 1024):
    """Download image from official website and convert to base64 data URL for storage."""
    try:
        r = requests.get(img_url, headers=HEADERS, timeout=10)
        if r.status_code == 200 and len(r.content) <= max_bytes:
            content_type = r.headers.get('Content-Type', 'image/jpeg')
            if 'image' not in content_type:
                content_type = 'image/jpeg'
            b64_str = base64.b64encode(r.content).decode('ascii')
            return f"data:{content_type};base64,{b64_str}"
    except Exception:
        pass
    # If download failed or too large, return original URL
    return img_url


def scrape_official_product_details(product_url, catalogue_price, markup=300.0, download_images=True):
    """Scrape product details from the official product page URL.
    
    Extracts:
      - Title / Name
      - Overview / Description
      - Technical Specifications (key-value table)
      - Key Features / Highlights
      - Box Contents (What's in the box)
      - High-resolution product images (from official website)
      - Calculated price: sale_price = catalogue_price + markup
    """
    result = {
        'url': product_url,
        'title': '',
        'description': '',
        'specs_text': '',
        'specs_count': 0,
        'highlights_text': '',
        'highlights_count': 0,
        'box_contents_text': '',
        'image_path': None,
        'gallery_images': [],
        'official_price': None,
        'brand': '',
        'catalogue_price': catalogue_price,
        'cost_price': round(float(catalogue_price), 2),
        'sale_price': round(float(catalogue_price) + float(markup), 2),
        'markup': markup,
    }

    try:
        r = requests.get(product_url, headers=HEADERS, timeout=12)
        if r.status_code >= 400:
            return None
        soup = BeautifulSoup(r.text, 'html.parser')
    except Exception:
        return None

    raw_images = []
    specs_list = []
    highlights_list = []
    box_list = []

    # ── 1. JSON-LD Schema.org Product Extraction ──────────────────────
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            ld = json.loads(script.string or '')
            items = ld if isinstance(ld, list) else [ld]
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_type = item.get('@type', '')
                if item_type == 'Product' or (isinstance(item_type, list) and 'Product' in item_type):
                    if not result['title']:
                        result['title'] = item.get('name', '').strip()
                    if not result['description']:
                        result['description'] = item.get('description', '').strip()

                    # Brand
                    b_obj = item.get('brand')
                    if isinstance(b_obj, dict):
                        result['brand'] = b_obj.get('name', '')
                    elif isinstance(b_obj, str):
                        result['brand'] = b_obj

                    # Images from JSON-LD
                    imgs = item.get('image', [])
                    if isinstance(imgs, str):
                        imgs = [imgs]
                    for img in imgs:
                        if isinstance(img, str) and img.startswith('http'):
                            raw_images.append(img)
                        elif isinstance(img, dict) and img.get('url'):
                            raw_images.append(img.get('url'))

                    # Official listed price if available
                    offers = item.get('offers')
                    if isinstance(offers, dict) and offers.get('price'):
                        result['official_price'] = float(offers['price'])
                    elif isinstance(offers, list) and offers and offers[0].get('price'):
                        result['official_price'] = float(offers[0]['price'])

                    # Additional Specs properties
                    props = item.get('additionalProperty', [])
                    for p in props:
                        if isinstance(p, dict) and p.get('name') and p.get('value'):
                            specs_list.append(f"{p['name']}: {p['value']}")
        except Exception:
            pass

    # ── 2. Meta Tags Fallback ─────────────────────────────────────────
    if not result['title']:
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            result['title'] = og_title['content'].strip()
        elif soup.find('h1'):
            result['title'] = soup.find('h1').get_text(strip=True)
        elif soup.title:
            result['title'] = soup.title.string.strip()

    if not result['description']:
        og_desc = soup.find('meta', property='og:description') or soup.find('meta', attrs={'name': 'description'})
        if og_desc and og_desc.get('content'):
            result['description'] = og_desc['content'].strip()

    og_image = soup.find('meta', property='og:image')
    if og_image and og_image.get('content') and og_image['content'].startswith('http'):
        if og_image['content'] not in raw_images:
            raw_images.insert(0, og_image['content'])

    # ── 3. Tech Specs Extraction (Tables, DLs, Spec containers) ────────
    # Check tables
    for table in soup.find_all('table'):
        for tr in table.find_all('tr'):
            cols = tr.find_all(['td', 'th'])
            if len(cols) == 2:
                k = cols[0].get_text(strip=True)
                v = cols[1].get_text(strip=True)
                if k and v and len(k) < 60 and len(v) < 300:
                    specs_list.append(f"{k}: {v}")

    # Check definition lists <dl><dt><dd>
    for dl in soup.find_all('dl'):
        dts = dl.find_all('dt')
        dds = dl.find_all('dd')
        for dt, dd in zip(dts, dds):
            k = dt.get_text(strip=True)
            v = dd.get_text(strip=True)
            if k and v and len(k) < 60 and len(v) < 300:
                specs_list.append(f"{k}: {v}")

    # Check specific spec classes (e.g. .specification-row, .tech-specs, .specs-item)
    for row in soup.select('.specification, .tech-spec, .spec-item, .product-property, .attribute-row'):
        txt = row.get_text(':', strip=True)
        if ':' in txt:
            parts = txt.split(':', 1)
            if len(parts[0]) < 60 and len(parts[1]) < 300:
                specs_list.append(f"{parts[0].strip()}: {parts[1].strip()}")

    # ── 4. Key Features / Highlights Extraction ───────────────────────
    # Look for bullet points inside feature or description sections
    feature_containers = soup.select(
        '.features, .key-features, .product-features, .highlights, .bullet-points, '
        '#features, #highlights, .description ul, .product-description ul'
    )
    for container in feature_containers:
        for li in container.find_all('li'):
            li_txt = li.get_text(strip=True)
            if li_txt and len(li_txt) >= 8 and len(li_txt) <= 250:
                highlights_list.append(li_txt)

    # ── 5. What's In The Box / Package Contents Extraction ─────────────
    box_containers = soup.find_all(
        lambda tag: tag.name in ['div', 'section', 'ul'] and any(
            b in (tag.get('id', '') + ' ' + ' '.join(tag.get('class', []))).lower()
            for b in ['box', 'package', 'included', 'contents']
        )
    )
    for b_el in box_containers:
        for li in b_el.find_all('li'):
            b_txt = li.get_text(strip=True)
            if b_txt and len(b_txt) >= 3 and len(b_txt) <= 120:
                box_list.append(b_txt)

    # ── 6. Website High-Res Gallery Images Extraction ──────────────────
    gallery_selectors = [
        '.product-media img', '.product-gallery img', '.product-images img',
        '.main-image img', '.woocommerce-product-gallery img', 'img[src*="/products/"]'
    ]
    for sel in gallery_selectors:
        for img in soup.select(sel):
            src = img.get('data-src') or img.get('data-zoom') or img.get('src')
            if src:
                src_full = urllib.parse.urljoin(product_url, src)
                if src_full.startswith('http') and not any(bad in src_full.lower() for bad in ['logo', 'icon', 'spinner', 'badge']):
                    if src_full not in raw_images:
                        raw_images.append(src_full)

    # Clean duplicates while preserving order
    clean_images = []
    seen = set()
    for img_url in raw_images:
        # Strip query parameters for deduplication (e.g. ?v=123)
        base = img_url.split('?')[0]
        if base not in seen:
            seen.add(base)
            clean_images.append(img_url)

    # If download_images is requested, convert main image and up to 4 gallery images
    if clean_images:
        primary_img_url = clean_images[0]
        if download_images:
            result['image_path'] = _download_image_as_data_url(primary_img_url)
        else:
            result['image_path'] = primary_img_url

        for gal_url in clean_images[1:6]:
            if download_images:
                result['gallery_images'].append(_download_image_as_data_url(gal_url))
            else:
                result['gallery_images'].append(gal_url)

    # Deduplicate and format specs text
    unique_specs = []
    specs_seen = set()
    for s in specs_list:
        s_norm = s.strip()
        if s_norm and s_norm.lower() not in specs_seen:
            specs_seen.add(s_norm.lower())
            unique_specs.append(s_norm)

    result['specs_text'] = '\n'.join(unique_specs[:25])
    result['specs_count'] = len(unique_specs[:25])

    # Deduplicate and format highlights
    unique_hl = []
    hl_seen = set()
    for h in highlights_list:
        h_norm = h.strip()
        if h_norm and h_norm.lower() not in hl_seen:
            hl_seen.add(h_norm.lower())
            unique_hl.append(h_norm)

    result['highlights_text'] = '\n'.join(unique_hl[:8])
    result['highlights_count'] = len(unique_hl[:8])

    # Deduplicate box contents
    unique_box = []
    box_seen = set()
    for b in box_list:
        b_norm = b.strip()
        if b_norm and b_norm.lower() not in box_seen:
            box_seen.add(b_norm.lower())
            unique_box.append(b_norm)

    result['box_contents_text'] = ', '.join(unique_box[:8])

    # Clean description (remove extra whitespace)
    if result['description']:
        result['description'] = re.sub(r'\s+', ' ', result['description']).strip()

    return result
