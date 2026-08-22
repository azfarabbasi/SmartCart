DEFAULTS = {
    'contact_phone': '+923312344418',
    'contact_email': 'azfar.aa.abbasi@gmail.com',
    'whatsapp_number': '923312344418',
    'top_badge_1_text': '100% Authentic Products',
    'top_badge_1_icon': 'bi-shield-check',
    'top_badge_2_text': 'Delivery All Over Karachi',
    'top_badge_2_icon': 'bi-truck',
    'delivery_scope_text': 'Delivery All Over Karachi',
    'hero_title': 'Welcome to SmartCart',
    'hero_subtitle': 'Browse our full catalog - fast delivery all over Karachi.',
    'checkout_notice': "Orders are dispatched once payment is verified. Delivery available all over Karachi.",
    'free_delivery_notice': 'FREE delivery on orders above Rs 2,000 in Karachi',
    'site_announcement': '',
    'footer_note': 'SmartCart - Premium Tech & Gadgets delivered across Karachi.',
    'bank_name': '',
    'bank_account_title': '',
    'bank_account_number': '',
    'bank_iban': '',
    'cod_advance_amount': '300',
    'cashback_points': '400',
    'min_profit_margin_floor': '300',
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
    ('Contact & Support Details', [
        ('contact_phone', 'Customer Support Phone Number', 'text'),
        ('contact_email', 'Customer Support Email Address', 'text'),
        ('whatsapp_number', 'WhatsApp Support Number (digits only with country code, e.g. 923312344418)', 'text'),
    ]),
    ('Storefront Messages & Notices', [
        ('hero_title', 'Homepage Hero Title', 'text'),
        ('hero_subtitle', 'Homepage Hero Subtitle', 'text'),
        ('free_delivery_notice', 'Free Delivery Promotion Notice', 'text'),
        ('checkout_notice', 'Checkout Page Notice / Delivery Policy', 'textarea'),
        ('site_announcement', 'Sitewide Announcement Banner (leave blank to hide)', 'textarea'),
        ('footer_note', 'Footer Copyright / Tagline Note', 'text'),
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
