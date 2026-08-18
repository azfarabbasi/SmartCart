import urllib.parse


def format_whatsapp_phone(phone):
    """
    Format any Pakistani or international phone number for WhatsApp direct messaging.
    Converts:
      '03212814435' -> '923212814435'
      '+92 321 2814435' -> '923212814435'
      '00923212814435' -> '923212814435'
      '3212814435' -> '923212814435'
    """
    if not phone:
        return ''
    digits = ''.join(ch for ch in str(phone) if ch.isdigit())
    if not digits:
        return ''
    if digits.startswith('0092'):
        digits = '92' + digits[4:]
    elif digits.startswith('92'):
        pass
    elif digits.startswith('0'):
        digits = '92' + digits[1:]
    elif len(digits) == 10 and digits.startswith('3'):
        digits = '92' + digits
    return digits


def get_whatsapp_order_link(phone, order_id, customer_name, total_amount, status='pending', payment_method='cod', address='', intent='status'):
    """
    Generate an instant WhatsApp deep-link with pre-filled message template
    tailored to the customer's order and current status.
    """
    phone_clean = format_whatsapp_phone(phone)
    if not phone_clean:
        return '#'

    name_clean = (customer_name or 'Customer').strip()
    status_clean = (status or 'pending').strip().lower()
    pay_clean = 'Cash on Delivery (COD)' if payment_method == 'cod' else 'Online Bank Transfer'
    amount_str = f"Rs. {float(total_amount):,.2f}" if total_amount is not None else "Rs. 0.00"
    addr_clean = (address or 'Karachi').strip()

    if intent == 'verify_request':
        msg = (
            f"Assalam-o-Alaikum {name_clean},\n\n"
            f"This is SmartCart regarding your Order #{order_id} ({amount_str}).\n\n"
            f"Please share your online payment bank transfer screenshot / receipt here so our team can verify your payment and prepare your order for dispatch.\n\n"
            f"Thank you for shopping with SmartCart! 🛒"
        )
    elif intent == 'payment_verified':
        msg = (
            f"Assalam-o-Alaikum {name_clean},\n\n"
            f"Your payment of {amount_str} for SmartCart Order #{order_id} has been VERIFIED! ✅\n\n"
            f"Your order is now being packed and will be dispatched soon. Thank you! 🛍️"
        )
    elif status_clean == 'shipped' or intent == 'shipped':
        cod_line = f"💰 Amount to pay on delivery: {amount_str}\n" if payment_method == 'cod' else "💰 Payment Status: Paid Online\n"
        msg = (
            f"Assalam-o-Alaikum {name_clean},\n\n"
            f"Great news! Your SmartCart Order #{order_id} has been SHIPPED and is on its way to you! 🚚\n\n"
            f"📦 Order Summary:\n"
            f"• Amount: {amount_str}\n"
            f"• Payment: {pay_clean}\n"
            f"{cod_line}"
            f"📍 Delivery Address: {addr_clean}\n\n"
            f"Our rider will contact you upon arrival. Thank you for choosing SmartCart! 🛍️"
        )
    elif status_clean == 'delivered' or intent == 'delivered':
        msg = (
            f"Assalam-o-Alaikum {name_clean},\n\n"
            f"Your SmartCart Order #{order_id} ({amount_str}) has been successfully DELIVERED. 🎉\n\n"
            f"We hope you love your products! If you have any feedback or need assistance, feel free to reply to this chat.\n\n"
            f"Thank you for shopping with SmartCart! ⭐"
        )
    elif status_clean == 'cancelled' or intent == 'cancelled':
        msg = (
            f"Assalam-o-Alaikum {name_clean},\n\n"
            f"This is regarding your SmartCart Order #{order_id}.\n\n"
            f"Your order has been cancelled. If this was a mistake or you wish to place a new order, please reply to us here.\n\n"
            f"— SmartCart Support"
        )
    else:  # default / pending / confirmed
        cod_line = f"• Payment: Cash on Delivery ({amount_str})\n" if payment_method == 'cod' else f"• Payment: Online Bank Transfer ({amount_str})\n"
        msg = (
            f"Assalam-o-Alaikum {name_clean},\n\n"
            f"Thank you for your order at SmartCart!\n\n"
            f"📦 Order #{order_id} Details:\n"
            f"• Total Amount: {amount_str}\n"
            f"{cod_line}"
            f"• Status: Confirmed & Processing\n"
            f"• Delivery Address: {addr_clean}\n\n"
            f"We are preparing your package for delivery and will notify you as soon as it is dispatched.\n\n"
            f"Thank you for choosing SmartCart! 🛍️"
        )

    # Use https://api.whatsapp.com/send?phone=...&text=... for highest compatibility
    encoded_text = urllib.parse.quote(msg)
    return f"https://api.whatsapp.com/send?phone={phone_clean}&text={encoded_text}"
