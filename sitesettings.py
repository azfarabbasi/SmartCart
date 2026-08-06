DEFAULTS = {
    'contact_phone': '',
    'contact_email': '',
    'whatsapp_number': '',
    'hero_title': 'Welcome to SmartCart',
    'hero_subtitle': 'Browse our full catalog - no account needed to look around.',
    'checkout_notice': "Orders are dispatched once payment is verified. You'll receive an email once your payment is confirmed.",
    'site_announcement': '',
    'footer_note': '',
    'bank_name': '',
    'bank_account_title': '',
    'bank_account_number': '',
    'bank_iban': '',
    'cod_advance_amount': '300',
    'cashback_points': '400',
}

# Keys grouped for the admin settings form.
FIELD_GROUPS = [
    ('Contact Information', [
        ('contact_phone', 'Contact Phone', 'text'),
        ('contact_email', 'Contact Email', 'text'),
        ('whatsapp_number', 'WhatsApp Number (digits only, country code first, e.g. 923001234567)', 'text'),
    ]),
    ('Bank Transfer Details', [
        ('bank_name', 'Bank Name', 'text'),
        ('bank_account_title', 'Account Title', 'text'),
        ('bank_account_number', 'Account Number', 'text'),
        ('bank_iban', 'IBAN', 'text'),
    ]),
    ('Payment Amounts', [
        ('cod_advance_amount', 'Cash on Delivery advance (Rs)', 'number'),
        ('cashback_points', 'Bank transfer cashback (loyalty points, 2 pts = Rs. 1)', 'number'),
    ]),
    ('Site Messages', [
        ('hero_title', 'Homepage Hero Title', 'text'),
        ('hero_subtitle', 'Homepage Hero Subtitle', 'text'),
        ('checkout_notice', 'Checkout Notice', 'textarea'),
        ('site_announcement', 'Sitewide Announcement Banner (leave blank to hide)', 'textarea'),
        ('footer_note', 'Footer Note (optional, leave blank to hide)', 'text'),
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
