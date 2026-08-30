import re

_ICON_RULES = [
    (r'(?i)(battery|capacity|mah|cell|wh\b)', 'bi-battery-charging', '#10b981'),
    (r'(?i)(charging|fast charge|power|watt|output|input|pd\b|qc\b|22\.5w|20w|65w|100w|voltage|ampere|current)', 'bi-lightning-charge-fill', '#f59e0b'),
    (r'(?i)(port|usb|type-c|type c|lightning|micro usb|jack|pin|slot)', 'bi-usb-symbol', '#3b82f6'),
    (r'(?i)(dimension|size|length|width|height|thickness|measurement|mm\b|cm\b)', 'bi-aspect-ratio', '#8b5cf6'),
    (r'(?i)(weight|gram|g\b|kg\b|mass|lightweight)', 'bi-speedometer2', '#ec4899'),
    (r'(?i)(display|screen|indicator|led|lcd|digital|percentage)', 'bi-display', '#06b6d4'),
    (r'(?i)(bluetooth|wireless|connectivity|range|version|5\.\d|wifi|tws)', 'bi-bluetooth', '#2563eb'),
    (r'(?i)(audio|sound|driver|bass|anc|noise|frequency|speaker|earphone|headphone|mic|voice)', 'bi-soundwave', '#6366f1'),
    (r'(?i)(time|playtime|backup|standby|hours|charging time|endurance)', 'bi-clock-history', '#14b8a6'),
    (r'(?i)(warranty|guarantee|official|replacement|claim)', 'bi-shield-check', '#10b981'),
    (r'(?i)(material|build|casing|finish|body|aluminium|plastic)', 'bi-layers-fill', '#64748b'),
    (r'(?i)(compatib|devices|support|phone|iphone|android|samsung|universal)', 'bi-phone', '#0284c7'),
    (r'(?i)(model|sku|series|brand|code|name|edition)', 'bi-tag', '#f97316'),
    (r'(?i)(feature|protection|safety|sensor|chip|smart|processor)', 'bi-cpu', '#8b5cf6'),
]


def get_icon_for_key(key_text):
    """Return (bootstrap_icon_class, badge_color) based on spec key content."""
    text = str(key_text or '').strip()
    for pattern, icon, color in _ICON_RULES:
        if re.search(pattern, text):
            return icon, color
    return 'bi-check2-circle', '#eab308'


def parse_technical_specs(raw_text):
    """Smart parser for copy-pasted technical specifications.
    
    Accepts text with:
      - Key: Value
      - Key - Value
      - Key \t Value
      - [Section Name] or Category Headers
      - Bullet points
    
    Returns a list of section dicts:
      [
        {
          'title': 'General Specifications',
          'items': [
            {'key': 'Battery Capacity', 'value': '20,000mAh (74Wh)', 'icon': 'bi-battery-charging', 'color': '#10b981'},
            ...
          ]
        }
      ]
    """
    if not raw_text or not str(raw_text).strip():
        return []

    lines = str(raw_text).strip().splitlines()
    sections = []
    current_section = {'title': 'Technical Specifications', 'items': []}

    for line in lines:
        cleaned = line.strip()
        if not cleaned:
            continue

        # Strip leading markdown symbols / bullets
        cleaned = re.sub(r'^[•\-\*#>\s]+', '', cleaned).strip()
        if not cleaned:
            continue

        # Check if line is a Section Header, e.g. [BATTERY & CHARGING] or --- Ports --- or Section:
        header_match = re.match(r'^[\[\(\{\-~=_\s]*([A-Za-z0-9\s/&,]+)[\]\)\}\-~=_\s]*$', cleaned)
        if header_match and (cleaned.isupper() or cleaned.startswith('[') or cleaned.endswith(']') or cleaned.endswith(':') and not (':' in cleaned[:-1])):
            title = header_match.group(1).rstrip(':').strip()
            if len(title) >= 3 and len(title) <= 50 and not any(ch in title for ch in ['mAh', 'Watt', '22.5W', '20W', '18W', 'kg', 'mm', 'Rs']):
                if current_section['items']:
                    sections.append(current_section)
                current_section = {'title': title.title(), 'items': []}
                continue

        # Try key-value separators in order: tab, colon, pipe, dash
        key, value = None, None
        if '\t' in cleaned:
            parts = cleaned.split('\t', 1)
            key, value = parts[0].strip(), parts[1].strip()
        elif ':' in cleaned:
            # Handle markdown bold like **Capacity:** 20,000mAh
            m = re.match(r'^\*{0,2}([^:*]+)\*{0,2}\s*:\s*(.+)$', cleaned)
            if m:
                key, value = m.group(1).strip(), m.group(2).strip()
        elif ' - ' in cleaned:
            parts = cleaned.split(' - ', 1)
            key, value = parts[0].strip(), parts[1].strip()
        elif ' | ' in cleaned:
            parts = cleaned.split(' | ', 1)
            key, value = parts[0].strip(), parts[1].strip()

        if key and value:
            key = key.replace('**', '').replace('*', '').strip()
            value = value.replace('**', '').replace('*', '').strip()
            icon, color = get_icon_for_key(key)
            item_dict = {
                'key': key,
                'value': value,
                'icon': icon,
                'color': color,
            }
            current_section['items'].append(item_dict)
            if 'rows' not in current_section:
                current_section['rows'] = []
            current_section['rows'].append(item_dict)
        else:
            val = cleaned.replace('**', '').strip()
            icon, color = get_icon_for_key(val)
            item_dict = {
                'key': 'Feature',
                'value': val,
                'icon': icon,
                'color': color,
            }
            current_section['items'].append(item_dict)
            if 'rows' not in current_section:
                current_section['rows'] = []
            current_section['rows'].append(item_dict)

    if current_section['items']:
        sections.append(current_section)

    return sections


def parse_highlights_list(raw_highlights):
    """Parse comma/newline/bullet separated highlights into clean list with icons."""
    if not raw_highlights or not str(raw_highlights).strip():
        return []
    
    text = str(raw_highlights).strip()
    # Split by newline or comma or semicolon or pipe
    if '\n' in text:
        raw_items = text.splitlines()
    else:
        raw_items = re.split(r'[,|;]+', text)

    results = []
    for item in raw_items:
        clean = re.sub(r'^[•\-\*#>\s]+', '', item).strip()
        if clean:
            icon, color = get_icon_for_key(clean)
            results.append({'text': clean, 'icon': icon, 'color': color})
    return results


def parse_box_contents_list(raw_box):
    """Parse comma/newline/bullet separated box contents."""
    if not raw_box or not str(raw_box).strip():
        return []
    
    text = str(raw_box).strip()
    if '\n' in text:
        raw_items = text.splitlines()
    else:
        raw_items = re.split(r'[,|;]+', text)

    results = []
    for item in raw_items:
        clean = re.sub(r'^[•\-\*#>\s]+', '', item).strip()
        if clean:
            results.append(clean)
    return results
