DEFAULTS = {
    # 1. Contact & Social
    'contact_phone': '+923312344418',
    'contact_email': 'azfar.aa.abbasi@gmail.com',
    'whatsapp_number': '923312344418',
    'store_address': 'Gulistan-e-Jauhar, Karachi, Pakistan',
    'store_hours': 'Monday – Saturday: 11:00 AM – 11:00 PM',

    # 2. Header Perks & Trust Badges
    'top_badge_1_text': '100% Authentic Products',
    'top_badge_1_icon': 'bi-shield-check',
    'top_badge_2_text': 'Delivery All Over Karachi',
    'top_badge_2_icon': 'bi-truck',
    'delivery_scope_text': 'Delivery All Over Karachi',

    # 3. 4 Marketing Trust Value Pillars (Home & Product Pages)
    'prop_1_title': 'Check at Delivery & 1-Day Exchange',
    'prop_1_sub': 'Check on delivery. 24h device compatibility exchange',
    'prop_1_icon': 'bi-box-seam',
    'prop_2_title': '100% Genuine with Warranty',
    'prop_2_sub': 'Official tech brands with warranty claim support',
    'prop_2_icon': 'bi-patch-check-fill',
    'prop_3_title': 'Express Delivery in Karachi',
    'prop_3_sub': 'Same-day & next-day dispatch to your doorstep',
    'prop_3_icon': 'bi-truck',
    'prop_4_title': 'Instant WhatsApp Support',
    'prop_4_sub': 'Real human assistance & quick order tracking',
    'prop_4_icon': 'bi-chat-dots-fill',

    # 4. Storefront Hero & Messages
    'hero_title': 'Welcome to SmartCart',
    'hero_subtitle': 'Browse our full catalog - fast delivery all over Karachi.',
    'free_delivery_notice': 'FREE delivery on orders above Rs 2,000 in Karachi',
    'checkout_notice': 'Orders are dispatched once payment is verified. Check parcel at delivery. Delivery available all over Karachi.',
    'site_announcement': '',
    'footer_note': 'SmartCart - Premium Tech, Earbuds & Smart Gadgets. Warehouse at Gulistan-e-Jauhar, Karachi.',

    # 5. Return & Exchange Policy (Specific to Gulistan-e-Jauhar & 1-Day Exchange)
    'returns_policy_title': 'Check on Delivery & 1-Day Exchange Policy',
    'returns_policy_summary': 'Check your parcel at the time of delivery. Within 1 day, exchange if incompatible with your device at our Gulistan-e-Jauhar warehouse.',
    'returns_days': '1',
    'returns_warehouse_location': 'Gulistan-e-Jauhar, Karachi',
    'shipping_policy_title': 'Shipping & Delivery in Karachi',
    'shipping_policy_summary': 'Fast, safe delivery across all areas of Karachi with live tracking and COD.',
    'faq_title': 'Frequently Asked Questions',
    'about_title': 'About SmartCart',
    'about_summary': 'Your trusted Karachi-based destination for 100% genuine tech, audio accessories, and gadgets.',

    # 6. Pricing, Margins & Banking
    'min_profit_margin_floor': '300',
    'bank_name': '',
    'bank_account_title': '',
    'bank_account_number': '',
    'bank_iban': '',
    'cod_advance_amount': '300',
    'cashback_points': '400',
}

# Keys grouped for the admin settings form.
FIELD_GROUPS = [
    ('Header Perks & Top Bar Badges', [
        ('top_badge_1_text', 'Left Trust Badge Text (e.g. 100% Authentic Products)', 'text'),
        ('top_badge_1_icon', 'Left Trust Badge Bootstrap Icon (e.g. bi-shield-check, bi-patch-check)', 'text'),
        ('top_badge_2_text', 'Right Trust Badge Text (e.g. Delivery All Over Karachi)', 'text'),
        ('top_badge_2_icon', 'Right Trust Badge Bootstrap Icon (e.g. bi-truck, bi-geo-alt, bi-box-seam)', 'text'),
        ('delivery_scope_text', 'Delivery Region / Scope Label (e.g. Delivery All Over Karachi)', 'text'),
    ]),
    ('4 Marketing Trust Pillars (Home & Product Pages)', [
        ('prop_1_title', 'Pillar 1 Title (e.g. Check at Delivery & 1-Day Exchange)', 'text'),
        ('prop_1_sub', 'Pillar 1 Subtitle', 'text'),
        ('prop_1_icon', 'Pillar 1 Icon (e.g. bi-box-seam, bi-arrow-repeat)', 'text'),
        ('prop_2_title', 'Pillar 2 Title (e.g. 100% Genuine with Warranty)', 'text'),
        ('prop_2_sub', 'Pillar 2 Subtitle', 'text'),
        ('prop_2_icon', 'Pillar 2 Icon (e.g. bi-patch-check-fill)', 'text'),
        ('prop_3_title', 'Pillar 3 Title (e.g. Express Delivery in Karachi)', 'text'),
        ('prop_3_sub', 'Pillar 3 Subtitle', 'text'),
        ('prop_3_icon', 'Pillar 3 Icon (e.g. bi-truck)', 'text'),
        ('prop_4_title', 'Pillar 4 Title (e.g. Instant WhatsApp Support)', 'text'),
        ('prop_4_sub', 'Pillar 4 Subtitle', 'text'),
        ('prop_4_icon', 'Pillar 4 Icon (e.g. bi-chat-dots-fill)', 'text'),
    ]),
    ('Storefront Messages & Notices', [
        ('hero_title', 'Homepage Hero Title', 'text'),
        ('hero_subtitle', 'Homepage Hero Subtitle', 'text'),
        ('free_delivery_notice', 'Free Delivery Promotion Notice', 'text'),
        ('checkout_notice', 'Checkout Page Notice / Delivery Policy', 'textarea'),
        ('site_announcement', 'Sitewide Announcement Banner (leave blank to hide)', 'textarea'),
        ('footer_note', 'Footer Copyright / Tagline Note', 'text'),
    ]),
    ('Exchange & Return Policy (Admin Editable)', [
        ('returns_policy_title', 'Policy Page Title', 'text'),
        ('returns_policy_summary', 'Policy Page Summary Subtitle', 'textarea'),
        ('returns_days', 'Exchange Window (Days, e.g. 1)', 'number'),
        ('returns_warehouse_location', 'Warehouse / Exchange Return Location (e.g. Gulistan-e-Jauhar, Karachi)', 'text'),
    ]),
    ('Customer Info Pages', [
        ('shipping_policy_title', 'Shipping Page Title', 'text'),
        ('shipping_policy_summary', 'Shipping Page Subtitle', 'textarea'),
        ('about_title', 'About Us Page Title', 'text'),
        ('about_summary', 'About Us Store Story / Summary', 'textarea'),
    ]),
    ('Contact & Support Details', [
        ('contact_phone', 'Customer Support Phone Number', 'text'),
        ('contact_email', 'Customer Support Email Address', 'text'),
        ('whatsapp_number', 'WhatsApp Support Number (digits only with country code, e.g. 923312344418)', 'text'),
        ('store_address', 'Store / Warehouse Physical Address', 'text'),
        ('store_hours', 'Operating Hours (e.g. Monday – Saturday: 11:00 AM – 11:00 PM)', 'text'),
    ]),
    ('Pricing & Margin Protection Floor', [
        ('min_profit_margin_floor', 'Minimum Profit Margin Floor (Rs per item) — Discounts & Loyalty points cannot reduce selling price below (Cost Price + this floor)', 'number'),
    ]),
    ('Bank Transfer Details', [
        ('bank_name', 'Bank Name (e.g. NayaPay, HBL, Meezan Bank, Sadapay)', 'text'),
        ('bank_account_title', 'Account Title (the exact name on the account)', 'text'),
        ('bank_account_number', 'Account Number / Mobile Wallet Number', 'text'),
        ('bank_iban', 'IBAN (optional — leave blank if not applicable)', 'text'),
    ]),
    ('Payment & Cashback Amounts', [
        ('cod_advance_amount', 'Cash on Delivery Advance Amount (Rs)', 'number'),
        ('cashback_points', 'Bank Transfer Cashback Points (10 pts = Rs. 1)', 'number'),
    ]),
]


def get_settings(cur):
    cur.execute("SELECT setting_key, setting_value FROM SiteSettings")
    values = dict(DEFAULTS)
    for key, value in cur.fetchall():
        if value is not None:
            values[key] = value
    return values


def get_setting_number(settings, key, default):
    try:
        return float(settings.get(key, default))
    except (TypeError, ValueError):
        return default
