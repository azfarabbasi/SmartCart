import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import quote

import oracledb
from flask import (Blueprint, abort, current_app, flash, redirect,
                    render_template, request, session, url_for)

import sitesettings
from activity import log_activity
from blueprints.auth.decorators import login_required
from auth_tokens import current_user_id
from db import get_db
from slugs import slugify
from uploads import process_upload, save_upload, validate_upload
from validators import validate_phone_pk, validate_required_text

customer_bp = Blueprint('customer', __name__)

LOW_STOCK_THRESHOLD = 5


from specs_parser import parse_technical_specs, parse_highlights_list, parse_box_contents_list
from whatsapp_utils import format_whatsapp_phone, get_whatsapp_order_link


def whatsapp_link(phone, message):
    phone_clean = format_whatsapp_phone(phone)
    if not phone_clean:
        return '#'
    return f'https://api.whatsapp.com/send?phone={phone_clean}&text={quote(message)}'



def notify_admin_stock_issue(cur, product_name, requested, available, customer_name, customer_email):
    settings = sitesettings.get_settings(cur)
    admin_email = settings.get('contact_email') or current_app.config.get('CONTACT_EMAIL')
    if not admin_email:
        return
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'SmartCart stock alert: {product_name}'
        msg['From'] = current_app.config['EMAIL_USER']
        msg['To'] = admin_email
        availability = 'is completely out of stock' if available <= 0 else f'only has {available} left in stock'
        body = f"""
        <html><body>
        <h2>Stock Alert</h2>
        <p>A customer encountered a stock limit while adding an item to their cart.</p>
        <ul>
            <li><strong>Product:</strong> {product_name}</li>
            <li><strong>Requested Quantity:</strong> {requested}</li>
            <li><strong>Available Stock:</strong> {available}</li>
            <li><strong>Customer:</strong> {customer_name} ({customer_email})</li>
        </ul>
        <p>The product {availability}. Please review inventory and restock if necessary.</p>
        </body></html>
        """
        msg.attach(MIMEText(body, 'html'))
        with smtplib.SMTP(current_app.config['EMAIL_SERVER'], current_app.config['EMAIL_PORT']) as server:
            server.starttls()
            server.login(current_app.config['EMAIL_USER'], current_app.config['EMAIL_PASSWORD'])
            server.send_message(msg)
    except Exception as e:
        current_app.logger.error(f'Failed to send stock alert email: {e}')


# ── PUBLIC CATALOG ──────────────────────────────────────────────
from cache_service import (get_all_categories, get_active_banners,
                           get_active_brands)

PRODUCT_SELECT = (
    "SELECT p.product_id, p.name, p.price, p.stock, CAST(NULL AS VARCHAR2(1)) AS description, "
    "p.image_path, c.category_name, p.delivery_time_text, p.free_delivery, "
    "b.brand_name, b.brand_id "
    "FROM Products p JOIN Categories c ON p.category_id = c.category_id "
    "LEFT JOIN Brands b ON p.brand_id = b.brand_id "
)


def _all_categories(cur=None):
    return get_all_categories(cur)


def _category_ids_for_slug(cur, slug):
    """All category ids whose name slugifies to `slug`."""
    matches = [(cid, name) for cid, name in _all_categories(cur) if slugify(name) == slug]
    if not matches:
        return [], None
    return [cid for cid, _ in matches], matches[0][1]


def _get_active_banners(cur=None):
    return get_active_banners(cur)


def _get_active_brands(cur=None):
    return get_active_brands(cur)


def _render_catalog(cur, products, heading, search='', active_slug=None):
    return render_template(
        'customer/home.html',
        products=products,
        categories=_all_categories(cur),
        hero_banners=_get_active_banners(cur),
        brands=_get_active_brands(cur),
        heading=heading,
        search=search,
        active_slug=active_slug,
    )


@customer_bp.route('/')
def index():
    # Old bookmarked/indexed links used query strings; send them to the
    # canonical path so nobody lands on a URL we no longer generate.
    legacy_category = request.args.get('category_id')
    legacy_search = request.args.get('search', '').strip()
    if legacy_category:
        cur = get_db().cursor()
        for cid, name in _all_categories(cur):
            if str(cid) == legacy_category:
                return redirect(url_for('customer.category', slug=slugify(name)), code=301)
        return redirect(url_for('customer.index'), code=301)
    if legacy_search:
        return redirect(url_for('customer.search', q=legacy_search), code=301)

    cur = get_db().cursor()
    cur.execute(PRODUCT_SELECT + "ORDER BY p.product_id")
    return _render_catalog(cur, cur.fetchall(), heading='Featured Products')


@customer_bp.route('/category/<slug>')
def category(slug):
    cur = get_db().cursor()
    category_ids, display_name = _category_ids_for_slug(cur, slug)
    if not category_ids:
        abort(404)

    binds = {f'c{i}': cid for i, cid in enumerate(category_ids)}
    placeholders = ', '.join(f':{key}' for key in binds)
    cur.execute(
        PRODUCT_SELECT + f"WHERE p.category_id IN ({placeholders}) ORDER BY p.product_id",
        binds,
    )
    return _render_catalog(cur, cur.fetchall(), heading=display_name, active_slug=slug)


@customer_bp.route('/search')
def search():
    term = request.args.get('q', '').strip()
    slug = request.args.get('category', '').strip()

    cur = get_db().cursor()
    if not term and not slug:
        return redirect(url_for('customer.index'))
    if not term and slug:
        return redirect(url_for('customer.category', slug=slug))

    clauses, binds = [], {}
    if term:
        clauses.append("(LOWER(p.name) LIKE :term OR LOWER(b.brand_name) LIKE :term)")
        binds['term'] = f'%{term.lower()}%'
    if slug:
        category_ids, _ = _category_ids_for_slug(cur, slug)
        if category_ids:
            id_binds = {f'c{i}': cid for i, cid in enumerate(category_ids)}
            binds.update(id_binds)
            clauses.append("p.category_id IN (%s)" % ', '.join(f':{k}' for k in id_binds))

    cur.execute(
        PRODUCT_SELECT + "WHERE " + " AND ".join(clauses) + " ORDER BY p.product_id",
        binds,
    )
    products = cur.fetchall()
    return _render_catalog(
        cur, products, heading=f'Search results for "{term}"', search=term, active_slug=slug or None,
    )


@customer_bp.route('/product/<int:product_id>')
def product_detail(product_id):
    cur = get_db().cursor()
    try:
        cur.execute(
            "SELECT p.product_id, p.name, p.price, p.stock, p.description, "
            "p.image_path, c.category_name, p.delivery_time_text, p.free_delivery, "
            "p.technical_specs, p.highlights, p.box_contents, "
            "b.brand_name, b.badge_text, b.badge_color, b.logo_path, b.brand_id "
            "FROM Products p JOIN Categories c ON p.category_id = c.category_id "
            "LEFT JOIN Brands b ON p.brand_id = b.brand_id "
            "WHERE p.product_id = :pid",
            {'pid': product_id},
        )
        product = cur.fetchone()
    except Exception:
        cur.execute(
            "SELECT p.product_id, p.name, p.price, p.stock, p.description, "
            "p.image_path, c.category_name, p.delivery_time_text, p.free_delivery, "
            "NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL "
            "FROM Products p JOIN Categories c ON p.category_id = c.category_id "
            "WHERE p.product_id = :pid",
            {'pid': product_id},
        )
        product = cur.fetchone()

    if not product:
        flash('Product not found.', 'error')
        return redirect(url_for('customer.index'))

    cur.execute(
        "SELECT media_id, media_path, media_type FROM ProductMedia "
        "WHERE product_id = :pid ORDER BY sort_order, media_id",
        {'pid': product_id},
    )
    gallery = cur.fetchall()

    # Query Color Variants
    try:
        cur.execute(
            "SELECT color_id, color_name, color_code, image_path, stock FROM ProductColors "
            "WHERE product_id = :pid ORDER BY sort_order, color_id",
            {'pid': product_id},
        )
        color_rows = cur.fetchall()
    except Exception:
        color_rows = []

    colors = []
    for cr in color_rows:
        colors.append({
            'id': cr[0],
            'name': cr[1],
            'code': cr[2] or '#000000',
            'image': cr[3],
            'stock': cr[4] or 0,
        })

    # Build unified media_list with cover image first, followed by gallery images/videos
    media_list = []
    seen = set()
    if product[5] and str(product[5]).strip():
        media_list.append({'id': 'cover', 'path': product[5], 'type': 'image'})
        seen.add(str(product[5]).strip())
    for item in gallery:
        m_id, m_path, m_type = item
        if m_path and str(m_path).strip() and str(m_path).strip() not in seen:
            media_list.append({'id': m_id, 'path': m_path, 'type': m_type or 'image'})
            seen.add(str(m_path).strip())

    # Parse Specs, Highlights, and Box Contents
    raw_specs = product[9] if len(product) > 9 else None
    raw_highlights = product[10] if len(product) > 10 else None
    raw_box = product[11] if len(product) > 11 else None

    parsed_specs = parse_technical_specs(raw_specs)
    parsed_highlights = parse_highlights_list(raw_highlights)
    parsed_box = parse_box_contents_list(raw_box)

    brand_info = None
    if len(product) > 12 and product[12]:
        brand_info = {
            'name': product[12],
            'badge_text': product[13],
            'badge_color': product[14] or 'brand-bg-dark',
            'logo': product[15],
            'id': product[16],
        }

    cur.execute(
        """
        SELECT f.feedback_id, u.name, f.rating, f.comment_text, f.media_path, f.media_type, f.created_at
        FROM ProductFeedback f JOIN Users u ON f.user_id = u.user_id
        WHERE f.product_id = :pid ORDER BY f.created_at DESC
        """,
        {'pid': product_id},
    )
    feedback_rows = cur.fetchall()
    feedback_list = []
    for fb in feedback_rows:
        cur.execute(
            """
            SELECT r.reply_text, r.media_path, r.media_type, r.created_at, u.name
            FROM FeedbackReplies r JOIN Users u ON r.admin_user_id = u.user_id
            WHERE r.feedback_id = :fid ORDER BY r.created_at
            """,
            {'fid': fb[0]},
        )
        replies = cur.fetchall()
        feedback_list.append({'feedback': fb, 'replies': replies})

    if session.get('user_id'):
        log_activity(cur, current_user_id(), 'view_product', product_id=product_id)
        get_db().commit()

    return render_template(
        'customer/product_detail.html',
        product=product,
        media_list=media_list,
        gallery=gallery,
        feedback_list=feedback_list,
        colors=colors,
        specs=parsed_specs,
        highlights=parsed_highlights,
        box_contents=parsed_box,
        brand=brand_info,
    )


# ── CART ─────────────────────────────────────────────────────────
@customer_bp.route('/cart')
@login_required
def view_cart():
    cur = get_db().cursor()
    try:
        cur.execute(
            "SELECT c.cart_id, p.product_id, p.name, p.price, c.quantity, p.image_path, p.stock, c.selected_color "
            "FROM Cart c JOIN Products p ON c.product_id = p.product_id "
            "WHERE c.user_id = :1",
            [current_user_id()],
        )
        items = cur.fetchall()
    except Exception:
        cur.execute(
            "SELECT c.cart_id, p.product_id, p.name, p.price, c.quantity, p.image_path, p.stock, NULL "
            "FROM Cart c JOIN Products p ON c.product_id = p.product_id "
            "WHERE c.user_id = :1",
            [current_user_id()],
        )
        items = cur.fetchall()

    total = sum(row[3] * row[4] for row in items)
    stock_alert = session.pop('stock_alert', None)
    whatsapp_cta = None
    if stock_alert:
        message = (
            f"Hi! I wanted to order {stock_alert['requested']} of \"{stock_alert['product']}\" "
            f"but only {stock_alert['available']} {'was' if stock_alert['available'] == 1 else 'were'} available. "
            "Can you help me out?"
        )
        whatsapp_cta = whatsapp_link(current_app.config.get('WHATSAPP_NUMBER', ''), message)
    return render_template(
        'customer/cart.html', items=items, total=total,
        stock_alert=stock_alert, whatsapp_cta=whatsapp_cta,
    )


def _record_stock_conflict(cur, product_name, requested, available):
    cur.execute("SELECT name, email FROM Users WHERE user_id = :1", [current_user_id()])
    cust_name, cust_email = cur.fetchone()
    notify_admin_stock_issue(cur, product_name, requested, available, cust_name, cust_email)
    session['stock_alert'] = {'product': product_name, 'available': available, 'requested': requested}


@customer_bp.route('/cart/add', methods=['POST'])
@login_required
def add_to_cart():
    product_id = int(request.form['product_id'])
    quantity = int(request.form.get('quantity', 1))
    selected_color = request.form.get('selected_color', '').strip() or None

    cur = get_db().cursor()
    cur.execute("SELECT name, stock FROM Products WHERE product_id = :1", [product_id])
    prod = cur.fetchone()
    if not prod:
        flash('Product not found.', 'error')
        return redirect(url_for('customer.index'))
    product_name, stock = prod

    if selected_color:
        try:
            cur.execute(
                "SELECT cart_id, quantity FROM Cart WHERE user_id = :1 AND product_id = :2 AND selected_color = :3",
                [current_user_id(), product_id, selected_color],
            )
            existing = cur.fetchone()
        except Exception:
            cur.execute(
                "SELECT cart_id, quantity FROM Cart WHERE user_id = :1 AND product_id = :2",
                [current_user_id(), product_id],
            )
            existing = cur.fetchone()
    else:
        try:
            cur.execute(
                "SELECT cart_id, quantity FROM Cart WHERE user_id = :1 AND product_id = :2 AND (selected_color IS NULL OR selected_color = '')",
                [current_user_id(), product_id],
            )
            existing = cur.fetchone()
        except Exception:
            cur.execute(
                "SELECT cart_id, quantity FROM Cart WHERE user_id = :1 AND product_id = :2",
                [current_user_id(), product_id],
            )
            existing = cur.fetchone()

    current_qty = existing[1] if existing else 0
    desired_total = current_qty + quantity

    if desired_total > stock:
        capped = max(stock, 0)
        if existing:
            cur.execute("UPDATE Cart SET quantity = :1 WHERE cart_id = :2", [capped, existing[0]])
        elif capped > 0:
            try:
                cur.execute(
                    "INSERT INTO Cart (cart_id, user_id, product_id, quantity, selected_color) "
                    "VALUES (cart_seq.NEXTVAL, :1, :2, :3, :4)",
                    [current_user_id(), product_id, capped, selected_color],
                )
            except Exception:
                cur.execute(
                    "INSERT INTO Cart (cart_id, user_id, product_id, quantity) "
                    "VALUES (cart_seq.NEXTVAL, :1, :2, :3)",
                    [current_user_id(), product_id, capped],
                )
        _record_stock_conflict(cur, product_name, desired_total, stock)
        log_activity(cur, current_user_id(), 'add_to_cart', product_id=product_id)
        get_db().commit()
        if stock <= 0:
            flash(f'Sorry, "{product_name}" is currently out of stock.', 'error')
        else:
            flash(
                f'Only {stock} of "{product_name}" {"is" if stock == 1 else "are"} available -- '
                'we\'ve added the most we have in stock.', 'error',
            )
        return redirect(url_for('customer.view_cart'))

    if existing:
        cur.execute(
            "UPDATE Cart SET quantity = quantity + :1 WHERE cart_id = :2",
            [quantity, existing[0]],
        )
    else:
        try:
            cur.execute(
                "INSERT INTO Cart (cart_id, user_id, product_id, quantity, selected_color) "
                "VALUES (cart_seq.NEXTVAL, :1, :2, :3, :4)",
                [current_user_id(), product_id, quantity, selected_color],
            )
        except Exception:
            cur.execute(
                "INSERT INTO Cart (cart_id, user_id, product_id, quantity) "
                "VALUES (cart_seq.NEXTVAL, :1, :2, :3)",
                [current_user_id(), product_id, quantity],
            )
    log_activity(cur, current_user_id(), 'add_to_cart', product_id=product_id)
    get_db().commit()
    flash('Item added to cart.', 'success')
    return redirect(url_for('customer.view_cart'))



@customer_bp.route('/cart/update', methods=['POST'])
@login_required
def update_cart():
    cart_id = int(request.form['cart_id'])
    quantity = int(request.form['quantity'])

    cur = get_db().cursor()
    if quantity <= 0:
        cur.execute(
            "DELETE FROM Cart WHERE cart_id = :1 AND user_id = :2",
            [cart_id, current_user_id()],
        )
        get_db().commit()
        return redirect(url_for('customer.view_cart'))

    cur.execute(
        "SELECT p.name, p.stock FROM Cart c JOIN Products p ON c.product_id = p.product_id "
        "WHERE c.cart_id = :1 AND c.user_id = :2",
        [cart_id, current_user_id()],
    )
    row = cur.fetchone()
    if not row:
        return redirect(url_for('customer.view_cart'))
    product_name, stock = row

    if quantity > stock:
        capped = max(stock, 0)
        if capped > 0:
            cur.execute(
                "UPDATE Cart SET quantity = :1 WHERE cart_id = :2 AND user_id = :3",
                [capped, cart_id, current_user_id()],
            )
        else:
            cur.execute("DELETE FROM Cart WHERE cart_id = :1 AND user_id = :2", [cart_id, current_user_id()])
        _record_stock_conflict(cur, product_name, quantity, stock)
        get_db().commit()
        if stock <= 0:
            flash(f'Sorry, "{product_name}" just sold out and was removed from your cart.', 'error')
        else:
            flash(f'Only {stock} of "{product_name}" available -- quantity adjusted.', 'error')
        return redirect(url_for('customer.view_cart'))

    cur.execute(
        "UPDATE Cart SET quantity = :1 WHERE cart_id = :2 AND user_id = :3",
        [quantity, cart_id, current_user_id()],
    )
    get_db().commit()
    return redirect(url_for('customer.view_cart'))


@customer_bp.route('/cart/remove/<int:cart_id>', methods=['POST'])
@login_required
def remove_from_cart(cart_id):
    cur = get_db().cursor()
    cur.execute(
        "DELETE FROM Cart WHERE cart_id = :1 AND user_id = :2",
        [cart_id, current_user_id()],
    )
    get_db().commit()
    flash('Item removed from cart.', 'success')
    return redirect(url_for('customer.view_cart'))


# ── WISHLIST ─────────────────────────────────────────────────────
@customer_bp.route('/wishlist')
@login_required
def view_wishlist():
    cur = get_db().cursor()
    cur.execute(
        "SELECT w.wishlist_id, p.product_id, p.name, p.price, p.image_path "
        "FROM Wishlist w JOIN Products p ON w.product_id = p.product_id "
        "WHERE w.user_id = :1",
        [current_user_id()],
    )
    items = cur.fetchall()
    return render_template('customer/wishlist.html', items=items)


@customer_bp.route('/wishlist/add', methods=['POST'])
@login_required
def add_to_wishlist():
    product_id = int(request.form['product_id'])
    cur = get_db().cursor()
    cur.execute(
        "SELECT COUNT(*) FROM Wishlist WHERE user_id = :1 AND product_id = :2",
        [current_user_id(), product_id],
    )
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO Wishlist (wishlist_id, user_id, product_id) "
            "VALUES (wishlist_seq.NEXTVAL, :1, :2)",
            [current_user_id(), product_id],
        )
        get_db().commit()
        flash('Added to wishlist.', 'success')
    else:
        flash('Already in wishlist.', 'info')
    return redirect(url_for('customer.view_wishlist'))


@customer_bp.route('/wishlist/remove/<int:wishlist_id>', methods=['POST'])
@login_required
def remove_from_wishlist(wishlist_id):
    cur = get_db().cursor()
    cur.execute(
        "DELETE FROM Wishlist WHERE wishlist_id = :1 AND user_id = :2",
        [wishlist_id, current_user_id()],
    )
    get_db().commit()
    return redirect(url_for('customer.view_wishlist'))


def _get_checkout_summary(cur, user_id, points_balance):
    try:
        cur.execute(
            "SELECT p.name, c.quantity, p.price, NVL(p.cost_price, 0), c.selected_color FROM Cart c JOIN Products p ON c.product_id = p.product_id "
            "WHERE c.user_id = :1",
            [user_id],
        )
        cart_rows = cur.fetchall()
        cart_items = [(r[0], r[1], float(r[2]), r[4] if len(r) > 4 else None) for r in cart_rows]
    except Exception:
        cur.execute(
            "SELECT p.name, c.quantity, p.price, NVL(p.cost_price, 0) FROM Cart c JOIN Products p ON c.product_id = p.product_id "
            "WHERE c.user_id = :1",
            [user_id],
        )
        cart_rows = cur.fetchall()
        cart_items = [(r[0], r[1], float(r[2]), None) for r in cart_rows]
    subtotal = sum(row[1] * float(row[2]) for row in cart_rows)
    settings = sitesettings.get_settings(cur)
    floor_margin = sitesettings.get_setting_number(settings, 'min_profit_margin_floor', 300)
    min_floor_price = sum(row[1] * (float(row[3]) + floor_margin) for row in cart_rows)
    max_total_discount = max(0.0, subtotal - min_floor_price)
    max_redeemable_points = int(min(points_balance, subtotal * 0.5 * 10, max_total_discount * 10))
    return {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'points_balance': points_balance,
        'max_redeemable_points': max_redeemable_points,
        'settings': settings,
    }


def _get_user_default_address(cur, user_id):
    try:
        cur.execute(
            """
            SELECT * FROM (
                SELECT phone_number, address_city, address_area, address_house_no,
                       address_block_sector, address_landmark, address_notes
                FROM Orders
                WHERE user_id = :1 AND (phone_number IS NOT NULL OR address_area IS NOT NULL)
                ORDER BY order_date DESC, order_id DESC
            ) WHERE ROWNUM = 1
            """,
            [user_id],
        )
        row = cur.fetchone()
        if row:
            return {
                'phone': row[0] or '',
                'address_city': row[1] or 'Karachi',
                'address_area': row[2] or '',
                'address_house_no': row[3] or '',
                'address_block_sector': row[4] or '',
                'address_landmark': row[5] or '',
                'address_notes': row[6] or '',
            }
    except Exception:
        pass
    return {
        'phone': '',
        'address_city': 'Karachi',
        'address_area': '',
        'address_house_no': '',
        'address_block_sector': '',
        'address_landmark': '',
        'address_notes': '',
    }


# ── CHECKOUT / ORDERS ────────────────────────────────────────────
@customer_bp.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cur = get_db().cursor()
    cur.execute("SELECT NVL(loyalty_points_balance, 0) FROM Users WHERE user_id = :1", [current_user_id()])
    row = cur.fetchone()
    points_balance = int(row[0]) if row and row[0] is not None else 0

    if request.method == 'POST':
        payment_method = request.form.get('payment_method', 'cod')
        phone = (request.form.get('phone', '') or '').strip().replace(' ', '').replace('-', '')
        city = (request.form.get('address_city', '') or '').strip()
        area = (request.form.get('address_area', '') or '').strip()
        house_no = (request.form.get('address_house_no', '') or '').strip()
        block_sector = (request.form.get('address_block_sector', '') or '').strip()
        landmark = (request.form.get('address_landmark', '') or '').strip()
        address_notes = (request.form.get('address_notes', '') or '').strip()
        coupon_code = (request.form.get('coupon_code', '') or '').strip() or None
        try:
            points_to_redeem = int(request.form.get('points_to_redeem', 0) or 0)
        except ValueError:
            points_to_redeem = 0

        ok, err, invalid_field = (True, None, None)
        if city != 'Karachi':
            ok, err, invalid_field = False, 'We currently only deliver in Karachi.', 'address_city'
        if ok:
            ok, err = validate_phone_pk(phone)
            if not ok:
                invalid_field = 'phone'
        if ok:
            ok, err = validate_required_text(area, 'Area', min_len=2, max_len=150)
            if not ok:
                invalid_field = 'address_area'
        if ok:
            ok, err = validate_required_text(house_no, 'Flat No. / House No.', min_len=1, max_len=100)
            if not ok:
                invalid_field = 'address_house_no'
        if ok:
            ok, err = validate_required_text(landmark, 'Nearest landmark', min_len=2, max_len=150)
            if not ok:
                invalid_field = 'address_landmark'
        if ok and payment_method not in ('cod', 'bank_transfer'):
            ok, err, invalid_field = False, 'Invalid payment method.', 'payment_method'
        if not ok:
            flash(err, 'error')
            ctx = _get_checkout_summary(cur, current_user_id(), points_balance)
            return render_template(
                'customer/checkout.html',
                **ctx,
                form_data=request.form,
                default_data={},
                invalid_field=invalid_field,
            ), 400

        address_line_parts = [house_no]
        if block_sector:
            address_line_parts.append(block_sector)
        address_line_parts.append(area)
        address_line_parts.append(city)
        address = ', '.join(address_line_parts) + f' (Near {landmark})'
        if address_notes:
            address += f' -- {address_notes}'

        cur.execute("SELECT COUNT(*) FROM Cart WHERE user_id = :1", [current_user_id()])
        if cur.fetchone()[0] == 0:
            flash('Your cart is empty.', 'error')
            return redirect(url_for('customer.view_cart'))

        # Re-check stock right before placing the order -- items may have been
        # added to the cart earlier, before someone else bought them.
        cur.execute(
            "SELECT p.name, c.quantity, p.stock FROM Cart c "
            "JOIN Products p ON c.product_id = p.product_id WHERE c.user_id = :1",
            [current_user_id()],
        )
        for item_name, item_qty, item_stock in cur.fetchall():
            if item_qty > item_stock:
                _record_stock_conflict(cur, item_name, item_qty, item_stock)
                get_db().commit()
                if item_stock <= 0:
                    flash(f'Sorry, "{item_name}" just sold out. Please remove it from your cart to continue.', 'error')
                else:
                    flash(
                        f'Sorry, we only have {item_stock} of "{item_name}" left '
                        f'(you have {item_qty} in your cart). Please adjust the quantity to continue.', 'error',
                    )
                return redirect(url_for('customer.view_cart'))

        proof_path = None
        if payment_method == 'bank_transfer':
            proof_file = request.files.get('payment_proof')
            if not proof_file or not proof_file.filename:
                flash('Please upload a screenshot of your bank transfer as payment proof for online payment.', 'error')
                ctx = _get_checkout_summary(cur, current_user_id(), points_balance)
                return render_template(
                    'customer/checkout.html',
                    **ctx,
                    form_data=request.form,
                    default_data={},
                    invalid_field='payment_proof',
                ), 400
            proof_ok, proof_err, data_url, _kind = process_upload(proof_file, allow_video=False)
            if not proof_ok:
                flash(proof_err, 'error')
                ctx = _get_checkout_summary(cur, current_user_id(), points_balance)
                return render_template(
                    'customer/checkout.html',
                    **ctx,
                    form_data=request.form,
                    default_data={},
                    invalid_field='payment_proof',
                ), 400
            proof_path = data_url
            log_activity(cur, current_user_id(), 'payment_uploaded')
            get_db().commit()

        order_id_var = cur.var(int)
        final_total_var = cur.var(float)
        coupon_disc_var = cur.var(float)
        loyalty_disc_var = cur.var(float)
        points_redeemed_var = cur.var(int)
        advance_var = cur.var(float)

        settings = sitesettings.get_settings(cur)
        cod_advance_amount = 0 if payment_method == 'cod' else sitesettings.get_setting_number(settings, 'cod_advance_amount', 300)
        floor_margin = sitesettings.get_setting_number(settings, 'min_profit_margin_floor', 300)

        try:
            cur.callproc('place_order', [
                current_user_id(), payment_method, address, phone, proof_path,
                points_to_redeem, coupon_code, cod_advance_amount, floor_margin,
                order_id_var, final_total_var, coupon_disc_var, loyalty_disc_var,
                points_redeemed_var, advance_var,
            ])
            get_db().commit()

            new_order_id = order_id_var.getvalue()

            try:
                cur.execute(
                    "UPDATE Orders SET address_city=:c, address_area=:a, address_house_no=:h, "
                    "address_block_sector=:b, address_landmark=:l, address_notes=:n WHERE order_id=:oid",
                    {'c': city, 'a': area, 'h': house_no, 'b': block_sector or None,
                     'l': landmark, 'n': address_notes or None, 'oid': new_order_id},
                )
            except Exception as e:
                current_app.logger.warning(f'Updating structured address parts failed: {e}')

            log_activity(cur, current_user_id(), 'order_placed', order_id=new_order_id)
            get_db().commit()

            final_total = final_total_var.getvalue() or 0.0
            points_earned_estimate = 0
            if final_total >= 5000:
                points_earned_estimate = 100 + int((final_total - 5000) // 1000) * 20

            if payment_method == 'cod':
                msg = f'Order #{new_order_id} placed successfully! Please pay Rs. {final_total:,.2f} in cash on delivery.'
            else:
                msg = f'Order #{new_order_id} placed! Your payment verification is pending.'
            if points_redeemed_var.getvalue():
                msg += f' {points_redeemed_var.getvalue()} loyalty points redeemed.'
            if coupon_disc_var.getvalue():
                msg += f' Coupon saved you Rs. {coupon_disc_var.getvalue():,.2f}.'
            if points_earned_estimate:
                msg += f" You'll earn {points_earned_estimate} loyalty points once this order is delivered."
            flash(msg, 'success')
            return redirect(url_for('customer.order_detail', order_id=new_order_id))

        except oracledb.DatabaseError as e:
            get_db().rollback()
            error_msg = str(e)
            current_app.logger.error(f'Order placement DatabaseError: {error_msg}')
            if 'ORA-20001' in error_msg:
                m = re.search(
                    r'product "(?P<name>.+?)"\.? Requested: (?P<req>\d+),? Available: (?P<avail>\d+)',
                    error_msg,
                )
                if m:
                    name, req, avail = m.group('name'), int(m.group('req')), int(m.group('avail'))
                    try:
                        _record_stock_conflict(cur, name, req, avail)
                        get_db().commit()
                    except Exception:
                        pass
                    flash(
                        f'Sorry, "{name}" sold out just now (only {avail} left). '
                        'Please adjust the quantity in your cart to continue.', 'error',
                    )
                else:
                    flash('Sorry, one of your items just sold out. Please check your cart and try again.', 'error')
                return redirect(url_for('customer.view_cart'))
            elif 'ORA-20002' in error_msg:
                flash('Your cart is empty.', 'error')
                return redirect(url_for('customer.view_cart'))
            elif 'ORA-20003' in error_msg:
                flash('Invalid or expired coupon code. Please remove it and try again.', 'error')
                ctx = _get_checkout_summary(cur, current_user_id(), points_balance)
                return render_template(
                    'customer/checkout.html',
                    **ctx,
                    form_data=request.form,
                    default_data={},
                    invalid_field='coupon_code',
                ), 400
            elif 'ORA-20004' in error_msg:
                flash('You have already used this coupon code on a previous order.', 'error')
                ctx = _get_checkout_summary(cur, current_user_id(), points_balance)
                return render_template(
                    'customer/checkout.html',
                    **ctx,
                    form_data=request.form,
                    default_data={},
                    invalid_field='coupon_code',
                ), 400
            elif 'ORA-02290' in error_msg:
                current_app.logger.error(f'CHECK CONSTRAINT VIOLATED: {error_msg}')
                flash('Order could not be saved due to a database constraint error. Please contact support.', 'error')
                ctx = _get_checkout_summary(cur, current_user_id(), points_balance)
                return render_template(
                    'customer/checkout.html',
                    **ctx,
                    form_data=request.form,
                    default_data={},
                ), 400
            else:
                first_line = error_msg.split('\n')[0].strip()
                flash(f'Order could not be placed: {first_line}', 'error')
                ctx = _get_checkout_summary(cur, current_user_id(), points_balance)
                return render_template(
                    'customer/checkout.html',
                    **ctx,
                    form_data=request.form,
                    default_data={},
                ), 400
        except Exception as e:
            get_db().rollback()
            current_app.logger.exception(f'Unexpected error during checkout: {e}')
            flash(f'Order could not be placed. Please try again. ({type(e).__name__}: {str(e)[:200]})', 'error')
            ctx = _get_checkout_summary(cur, current_user_id(), points_balance)
            return render_template(
                'customer/checkout.html',
                **ctx,
                form_data=request.form,
                default_data={},
            ), 400

    # GET
    log_activity(cur, current_user_id(), 'checkout_start')
    get_db().commit()

    ctx = _get_checkout_summary(cur, current_user_id(), points_balance)
    default_data = _get_user_default_address(cur, current_user_id())
    return render_template(
        'customer/checkout.html',
        **ctx,
        form_data={},
        default_data=default_data,
        invalid_field=None,
    )


@customer_bp.route('/orders')
@login_required
def order_history():
    cur = get_db().cursor()
    cur.execute(
        "SELECT order_id, order_date, total_amount, status, payment_status "
        "FROM Orders WHERE user_id = :1 ORDER BY order_date DESC",
        [current_user_id()],
    )
    orders = cur.fetchall()
    return render_template('customer/orders.html', orders=orders)


@customer_bp.route('/orders/<int:order_id>')
@login_required
def order_detail(order_id):
    cur = get_db().cursor()
    cur.execute(
        """
        SELECT order_id, order_date, total_amount, status, phone_number, delivery_address,
               payment_method, payment_status, advance_amount, coupon_code, coupon_discount_amount,
               loyalty_points_redeemed, loyalty_discount_amount, loyalty_points_earned,
               cashback_points_awarded, payment_rejection_reason
        FROM Orders WHERE order_id = :1 AND user_id = :2
        """,
        [order_id, current_user_id()],
    )
    order = cur.fetchone()
    if not order:
        flash('Order not found.', 'error')
        return redirect(url_for('customer.order_history'))

    try:
        cur.execute(
            "SELECT p.name, oi.quantity, oi.unit_price, oi.selected_color "
            "FROM OrderItems oi JOIN Products p ON oi.product_id = p.product_id "
            "WHERE oi.order_id = :1",
            [order_id],
        )
        items = cur.fetchall()
    except Exception:
        cur.execute(
            "SELECT p.name, oi.quantity, oi.unit_price, NULL "
            "FROM OrderItems oi JOIN Products p ON oi.product_id = p.product_id "
            "WHERE oi.order_id = :1",
            [order_id],
        )
        items = cur.fetchall()

    cur.execute("SELECT amount, payment_date, method FROM Payments WHERE order_id = :1", [order_id])
    payment = cur.fetchone()

    total_amount = float(order[2]) if order[2] is not None else 0.0
    status = order[3] or 'pending'
    points_earned = order[13] or 0
    pending_points_estimate = 0
    if not points_earned and status != 'cancelled' and total_amount >= 5000:
        pending_points_estimate = 100 + int((total_amount - 5000) // 1000) * 20

    return render_template(
        'customer/order_detail.html', order=order, items=items, payment=payment,
        pending_points_estimate=pending_points_estimate,
    )


# ── PROFILE ──────────────────────────────────────────────────────
@customer_bp.route('/account/profile')
@login_required
def profile():
    cur = get_db().cursor()
    cur.execute(
        "SELECT name, email, role, created_at, loyalty_points_balance FROM Users WHERE user_id = :1",
        [current_user_id()],
    )
    user = cur.fetchone()

    cur.execute("SELECT COUNT(*) FROM Orders WHERE user_id = :1", [current_user_id()])
    order_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM Wishlist WHERE user_id = :1", [current_user_id()])
    wishlist_count = cur.fetchone()[0]

    # Oracle 11.2 doesn't support FETCH FIRST N ROWS ONLY, so use a ROWNUM subquery.
    cur.execute(
        """
        SELECT * FROM (
            SELECT ledger_id, order_id, entry_type, points, rupee_value, balance_after, created_at
            FROM LoyaltyLedger WHERE user_id = :1 ORDER BY created_at DESC
        ) WHERE ROWNUM <= 5
        """,
        [current_user_id()],
    )
    recent_ledger = cur.fetchall()

    return render_template(
        'customer/profile.html', user=user, order_count=order_count,
        wishlist_count=wishlist_count, recent_ledger=recent_ledger,
    )


# ── LOYALTY ──────────────────────────────────────────────────────
@customer_bp.route('/account/loyalty')
@login_required
def loyalty_history():
    cur = get_db().cursor()
    cur.execute("SELECT loyalty_points_balance FROM Users WHERE user_id = :1", [current_user_id()])
    balance = cur.fetchone()[0]
    cur.execute(
        """
        SELECT ledger_id, order_id, entry_type, points, rupee_value, balance_after, created_at
        FROM LoyaltyLedger WHERE user_id = :1 ORDER BY created_at DESC
        """,
        [current_user_id()],
    )
    ledger = cur.fetchall()
    return render_template('customer/loyalty_history.html', balance=balance, ledger=ledger)


# ── POLICIES & MARKETING INFO PAGES ──────────────────────────────
@customer_bp.route('/returns')
def returns_policy():
    return render_template('customer/returns.html')


@customer_bp.route('/shipping')
def shipping_policy():
    return render_template('customer/shipping.html')


@customer_bp.route('/faq')
def faq():
    return render_template('customer/faq.html')


@customer_bp.route('/about')
def about():
    return render_template('customer/about.html')

