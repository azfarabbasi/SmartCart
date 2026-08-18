import re

_PHONE_RE = re.compile(r'^(?:\+92|0)3\d{9}$')
_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
_COUPON_RE = re.compile(r'^[A-Z0-9_-]{3,30}$')


def validate_phone_pk(phone):
    phone = (phone or '').strip().replace(' ', '').replace('-', '')
    if not _PHONE_RE.match(phone):
        return False, 'Enter a valid Pakistani mobile number, e.g. 03001234567 or +923001234567.'
    return True, None


def validate_email_format(email):
    email = (email or '').strip()
    if not _EMAIL_RE.match(email):
        return False, 'Enter a valid email address.'
    return True, None


def validate_required_text(value, field_name, min_len=1, max_len=500):
    value = (value or '').strip()
    if len(value) < min_len:
        return False, f'{field_name} is required.'
    if len(value) > max_len:
        return False, f'{field_name} must be {max_len} characters or fewer.'
    return True, None


def validate_price(value):
    try:
        price = float(value)
    except (TypeError, ValueError):
        return False, 'Price must be a number.', None
    if price <= 0:
        return False, 'Price must be greater than 0.', None
    return True, None, price


def validate_cost_price(value):
    if value in (None, ''):
        return True, None, 0.0
    try:
        cost = float(value)
    except (TypeError, ValueError):
        return False, 'Cost price must be a number.', None
    if cost < 0:
        return False, 'Cost price cannot be negative.', None
    return True, None, cost


def validate_stock(value):
    try:
        stock = int(value)
    except (TypeError, ValueError):
        return False, 'Stock must be a whole number.', None
    if stock < 0:
        return False, 'Stock cannot be negative.', None
    return True, None, stock


def validate_rating(value):
    if value in (None, ''):
        return True, None, None
    try:
        rating = int(value)
    except (TypeError, ValueError):
        return False, 'Rating must be a number between 1 and 5.', None
    if not 1 <= rating <= 5:
        return False, 'Rating must be between 1 and 5.', None
    return True, None, rating


def validate_coupon_code_format(code):
    code = (code or '').strip().upper()
    if not _COUPON_RE.match(code):
        return False, 'Coupon code must be 3-30 characters: letters, numbers, - or _ only.', None
    return True, None, code


def validate_discount_percent(value):
    try:
        pct = float(value)
    except (TypeError, ValueError):
        return False, 'Discount percent must be a number.', None
    if not 1 <= pct <= 100:
        return False, 'Discount percent must be between 1 and 100.', None
    return True, None, pct


def validate_coupon_discount(discount_type, value):
    discount_type = (discount_type or 'percentage').strip().lower()
    if discount_type not in ('percentage', 'fixed'):
        return False, 'Discount type must be either percentage or fixed amount.', None
    try:
        val = float(value)
    except (TypeError, ValueError):
        return False, 'Discount value must be a valid number.', None
    if discount_type == 'percentage':
        if not 1 <= val <= 100:
            return False, 'Discount percent must be between 1% and 100%.', None
    else:
        if val <= 0:
            return False, 'Discount amount must be greater than Rs. 0.', None
    return True, None, val
