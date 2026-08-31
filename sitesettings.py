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
    'delivery_scope_text': 'Delivery All Over Karachi (4–5 Days, Rs 200)',

    # 3. 4 Marketing Trust Value Pillars (Home & Product Pages)
    'prop_1_title': 'Check at Delivery & 1-Day Exchange',
    'prop_1_sub': 'Check on delivery. 24h device compatibility exchange',
    'prop_1_icon': 'bi-box-seam',
    'prop_2_title': '100% Genuine with Warranty',
    'prop_2_sub': 'Official tech brands with warranty claim support',
    'prop_2_icon': 'bi-patch-check-fill',
    'prop_3_title': 'Delivery All Over Karachi',
    'prop_3_sub': 'Within 4–5 days after order confirmation (Rs 200)',
    'prop_3_icon': 'bi-truck',
    'prop_4_title': 'Instant WhatsApp Support',
    'prop_4_sub': 'Real human assistance & quick order tracking',
    'prop_4_icon': 'bi-chat-dots-fill',

    # 4. Storefront Hero & Messages
    'hero_title': 'Welcome to SmartCart',
    'hero_subtitle': 'Browse our full catalog - delivery all over Karachi within 4–5 days.',
    'free_delivery_notice': 'Standard delivery fee is Rs 200 across Karachi',
    'checkout_notice': 'Delivery within 4–5 days after order confirmation. Standard delivery fee is Rs 200. Check parcel at delivery.',
    'site_announcement': '',
    'footer_note': 'SmartCart - Premium Tech, Earbuds & Smart Gadgets. Warehouse at Gulistan-e-Jauhar, Karachi.',

    # 5. Return & Exchange Policy (Specific to Gulistan-e-Jauhar & 1-Day Exchange)
    'returns_policy_title': 'Check on Delivery & 1-Day Exchange Policy',
    'returns_policy_summary': 'Check your parcel at the time of delivery. Within 1 day, exchange if incompatible with your device at our Gulistan-e-Jauhar warehouse.',
    'returns_days': '1',
    'returns_warehouse_location': 'Gulistan-e-Jauhar, Karachi',
    'returns_ineligible_items': "Items with physical damage, scratches or liquid ingress\nProducts with the packaging or seal destroyed\nEarphones and earbuds that have been used, for hygiene reasons — unless the item is faulty\nItems returned more than 1 day after delivery",
    'warranty_exclusions_items': "Physical damage, including cut or frayed cables\nWater or liquid damage\nDamage from use with a non-compliant charger or power source\nNormal battery capacity decline over time",

    # 6. Shipping & Delivery Details
    'shipping_policy_title': 'Shipping & Delivery in Karachi',
    'shipping_policy_summary': 'Delivery across all areas of Karachi within 4–5 days after order confirmation. Standard delivery fee is Rs 200.',
    'delivery_timeline_text': 'Within 4–5 days after order confirmation',
    'standard_delivery_fee': '200',
    'about_title': 'About SmartCart',
    'about_summary': 'Your trusted Karachi-based destination for 100% genuine tech, audio accessories, and gadgets.',

    # 7. Frequently Asked Questions (Live Editable FAQs 1 to 6)
    'faq_title': 'Frequently Asked Questions',
    'faq_subtitle': 'Got questions about delivery in Karachi, product authenticity, or 1-day exchange? Find quick answers below.',
    
    'faq_1_icon': 'bi-patch-check-fill',
    'faq_1_q': 'Are all products listed on SmartCart 100% original & authentic?',
    'faq_1_a': 'Yes, absolutely. We source all our electronics, audio devices, smartwatches, and accessories directly from authorized distributors and official brand importers (Ronin, Apple, Anker, Samsung, Sony, Razer, Audionic, Baseus). Every item is 100% brand new and covered by official local warranty.',
    
    'faq_2_icon': 'bi-box-seam',
    'faq_2_q': 'Can I check my product on delivery and exchange if not compatible?',
    'faq_2_a': 'Yes! You can check the product right at the time of delivery. Furthermore, within 1 day (24 hours), if you find the product is not compatible with your device, you can deliver it back to our warehouse in Gulistan-e-Jauhar, Karachi and exchange it with any other product from our store, provided the packaging and box are undamaged and the item is completely scratchless and unused.',
    
    'faq_3_icon': 'bi-truck',
    'faq_3_q': 'Do you deliver all over Karachi? What is the delivery time and fee?',
    'faq_3_a': 'Yes! We deliver across all areas of Karachi (Gulistan-e-Jauhar, Gulshan, DHA, Clifton, North Nazimabad, Malir, Bahria Town, Scheme 33, etc.). Delivery takes 4–5 days after order confirmation, and our standard flat delivery fee is Rs. 200.',
    
    'faq_4_icon': 'bi-credit-card-2-front',
    'faq_4_q': 'What payment methods do you accept?',
    'faq_4_a': 'We accept Direct Bank Transfer (NayaPay, Sadapay, HBL, Meezan Bank, etc.) with instant cashback loyalty points, and Cash on Delivery (COD) across Karachi with an advance booking deposit of Rs 300 (adjusted into your total invoice).',
    
    'faq_5_icon': 'bi-shield-lock-fill',
    'faq_5_q': 'How do I claim product warranty in Karachi?',
    'faq_5_a': "Warranty claims are managed directly with our Karachi customer support. You don't have to fill out complicated manufacturer forms; just send your Order ID and description of the technical issue to our WhatsApp team, and we will guide you through diagnosis or warranty replacement at our Gulistan-e-Jauhar location.",
    
    'faq_6_icon': 'bi-headset',
    'faq_6_q': 'How can I track my order or contact support?',
    'faq_6_a': 'You can message us directly on WhatsApp at +923312344418 with your Order ID for real-time status updates from our Karachi support team.',

    # 8. Pricing, Margins & Banking
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
        ('prop_3_title', 'Pillar 3 Title (e.g. Delivery All Over Karachi)', 'text'),
        ('prop_3_sub', 'Pillar 3 Subtitle (e.g. Within 4–5 days after order confirmation)', 'text'),
        ('prop_3_icon', 'Pillar 3 Icon (e.g. bi-truck)', 'text'),
        ('prop_4_title', 'Pillar 4 Title (e.g. Instant WhatsApp Support)', 'text'),
        ('prop_4_sub', 'Pillar 4 Subtitle', 'text'),
        ('prop_4_icon', 'Pillar 4 Icon (e.g. bi-chat-dots-fill)', 'text'),
    ]),
    ('Storefront Messages & Notices', [
        ('hero_title', 'Homepage Hero Title', 'text'),
        ('hero_subtitle', 'Homepage Hero Subtitle', 'text'),
        ('free_delivery_notice', 'Delivery Fee Promotion Notice (e.g. Standard delivery fee is Rs 200)', 'text'),
        ('checkout_notice', 'Checkout Page Notice / Delivery Policy', 'textarea'),
        ('site_announcement', 'Sitewide Announcement Banner (leave blank to hide)', 'textarea'),
        ('footer_note', 'Footer Copyright / Tagline Note', 'text'),
    ]),
    ('Shipping & Karachi Delivery Policy (Admin Editable)', [
        ('shipping_policy_title', 'Shipping Page Title', 'text'),
        ('shipping_policy_summary', 'Shipping Page Subtitle', 'textarea'),
        ('delivery_timeline_text', 'Delivery Timeline (e.g. Within 4–5 days after order confirmation)', 'text'),
        ('standard_delivery_fee', 'Standard Delivery Fee in Karachi (Rs, e.g. 200)', 'number'),
    ]),
    ('Exchange & Return Policy (Admin Editable)', [
        ('returns_policy_title', 'Policy Page Title', 'text'),
        ('returns_policy_summary', 'Policy Page Summary Subtitle', 'textarea'),
        ('returns_days', 'Exchange Window (Days, e.g. 1)', 'number'),
        ('returns_warehouse_location', 'Warehouse / Exchange Return Location (e.g. Gulistan-e-Jauhar, Karachi)', 'text'),
        ('returns_ineligible_items', 'What We Cannot Accept (1 item per line)', 'textarea'),
        ('warranty_exclusions_items', 'Not Covered by Warranty (1 item per line)', 'textarea'),
    ]),
    ('FAQ Settings & Questions (Admin Editable)', [
        ('faq_title', 'FAQ Page Main Title', 'text'),
        ('faq_subtitle', 'FAQ Page Subtitle / Introduction', 'textarea'),
        ('faq_1_icon', 'FAQ 1 Bootstrap Icon (e.g. bi-patch-check-fill)', 'text'),
        ('faq_1_q', 'FAQ 1 Question', 'text'),
        ('faq_1_a', 'FAQ 1 Answer', 'textarea'),
        ('faq_2_icon', 'FAQ 2 Bootstrap Icon (e.g. bi-box-seam)', 'text'),
        ('faq_2_q', 'FAQ 2 Question', 'text'),
        ('faq_2_a', 'FAQ 2 Answer', 'textarea'),
        ('faq_3_icon', 'FAQ 3 Bootstrap Icon (e.g. bi-truck)', 'text'),
        ('faq_3_q', 'FAQ 3 Question', 'text'),
        ('faq_3_a', 'FAQ 3 Answer', 'textarea'),
        ('faq_4_icon', 'FAQ 4 Bootstrap Icon (e.g. bi-credit-card-2-front)', 'text'),
        ('faq_4_q', 'FAQ 4 Question', 'text'),
        ('faq_4_a', 'FAQ 4 Answer', 'textarea'),
        ('faq_5_icon', 'FAQ 5 Bootstrap Icon (e.g. bi-shield-lock-fill)', 'text'),
        ('faq_5_q', 'FAQ 5 Question', 'text'),
        ('faq_5_a', 'FAQ 5 Answer', 'textarea'),
        ('faq_6_icon', 'FAQ 6 Bootstrap Icon (e.g. bi-headset)', 'text'),
        ('faq_6_q', 'FAQ 6 Question (leave blank to hide)', 'text'),
        ('faq_6_a', 'FAQ 6 Answer', 'textarea'),
    ]),
    ('Customer Info & About Us', [
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


def get_settings(cur=None):
    from cache_service import get_site_settings
    return get_site_settings(cur)


def get_setting_number(settings, key, default):
    try:
        return float(settings.get(key, default))
    except (TypeError, ValueError):
        return default
