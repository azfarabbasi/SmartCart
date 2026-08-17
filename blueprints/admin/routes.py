import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import quote

import oracledb
from flask import (Blueprint, current_app, flash, redirect, render_template,
                    request, url_for)

import sitesettings
from blueprints.auth.decorators import admin_required
from auth_tokens import current_user_id
from db import get_db
from extensions import limiter
from security import log_admin_action
from uploads import save_upload, validate_upload
from validators import (validate_cost_price, validate_discount_percent,
                         validate_price, validate_required_text, validate_stock)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
limiter.limit('60 per minute')(admin_bp)

MAX_PRODUCT_MEDIA = 10


def send_payment_verified_email(to_email, name, order_id, total_amount):
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'SmartCart - Payment Verified for Order #{order_id}'
        msg['From'] = current_app.config['EMAIL_USER']
        msg['To'] = to_email
        body = f"""
        <html><body>
        <h2>Hi {name},</h2>
        <p>Your payment for order <strong>#{order_id}</strong> (Rs. {total_amount:.2f}) has been verified.</p>
        <p>Your order will now be dispatched. Thank you for shopping with SmartCart!</p>
        <br><p>&mdash; The SmartCart Team</p>
        </body></html>
        """
        msg.attach(MIMEText(body, 'html'))
        server = smtplib.SMTP(current_app.config['EMAIL_HOST'], current_app.config['EMAIL_PORT'])
        server.starttls()
        server.login(current_app.config['EMAIL_USER'], current_app.config['EMAIL_PASSWORD'])
        server.sendmail(current_app.config['EMAIL_USER'], to_email, msg.as_string())
        server.quit()
    except Exception as e:
        current_app.logger.warning(f'Payment verified email failed: {e}')


def _whatsapp_link(phone, message):
    digits = ''.join(ch for ch in phone if ch.isdigit())
    if digits.startswith('0'):
        digits = '92' + digits[1:]
    elif not digits.startswith('92'):
        digits = '92' + digits
    return f'https://wa.me/{digits}?text={quote(message)}'


# ── DASHBOARD ────────────────────────────────────────────────────
@admin_bp.route('')
@admin_required
def dashboard():
    cur = get_db().cursor()
    cur.execute("SELECT COUNT(*) FROM Products")
    total_products = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM Orders")
    total_orders = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM Users WHERE role = 'customer'")
    total_customers = cur.fetchone()[0]
    cur.execute("SELECT NVL(SUM(total_amount), 0) FROM Orders WHERE status != 'cancelled'")
    total_revenue = float(cur.fetchone()[0])

    total_cost = 0.0
    try:
        cur.execute(
            """
            SELECT NVL(SUM(oi.quantity * NVL(p.cost_price, 0)), 0)
            FROM OrderItems oi
            JOIN Products p ON oi.product_id = p.product_id
            JOIN Orders o ON oi.order_id = o.order_id
            WHERE o.status != 'cancelled'
            """
        )
        total_cost = float(cur.fetchone()[0])
    except Exception as e:
        current_app.logger.warning(f"Error computing COGS in dashboard: {e}")
        total_cost = 0.0

    net_profit = total_revenue - total_cost
    profit_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0.0

    cur.execute("SELECT COUNT(*) FROM Orders WHERE payment_status = 'pending_verification'")
    pending_payments = cur.fetchone()[0]
    cur.execute(
        "SELECT order_id, name, order_date, total_amount, status FROM ("
        "  SELECT o.order_id, u.name, o.order_date, o.total_amount, o.status "
        "  FROM Orders o JOIN Users u ON o.user_id = u.user_id "
        "  ORDER BY o.order_date DESC"
        ") WHERE ROWNUM <= 5"
    )
    recent_orders = cur.fetchall()
    return render_template(
        'admin/dashboard.html', total_products=total_products, total_orders=total_orders,
        total_customers=total_customers, total_revenue=total_revenue, total_cost=total_cost,
        net_profit=net_profit, profit_margin=profit_margin,
        pending_payments=pending_payments, recent_orders=recent_orders,
    )


# ── PRODUCTS ─────────────────────────────────────────────────────
@admin_bp.route('/products')
@admin_required
def products():
    cur = get_db().cursor()
    try:
        cur.execute(
            "SELECT p.product_id, p.name, c.category_name, p.price, NVL(p.cost_price, 0), p.stock, p.image_path "
            "FROM Products p JOIN Categories c ON p.category_id = c.category_id "
            "ORDER BY p.product_id"
        )
        rows = cur.fetchall()
    except Exception as e:
        current_app.logger.warning(f"Fallback products query: {e}")
        cur.execute(
            "SELECT p.product_id, p.name, c.category_name, p.price, 0, p.stock, p.image_path "
            "FROM Products p JOIN Categories c ON p.category_id = c.category_id "
            "ORDER BY p.product_id"
        )
        rows = cur.fetchall()

    upload_dir = current_app.config['UPLOAD_FOLDER']
    product_rows = []
    for r in rows:
        pid, name, cat_name, price, cost_price, stock, img_path = r
        image_missing = bool(img_path) and not os.path.exists(os.path.join(upload_dir, os.path.basename(img_path)))
        unit_profit = float(price) - float(cost_price)
        margin_pct = (unit_profit / float(price) * 100) if float(price) > 0 else 0.0
        product_rows.append((pid, name, cat_name, price, cost_price, stock, img_path, image_missing, unit_profit, margin_pct))
    return render_template('admin/products.html', products=product_rows)


def _save_gallery_media(cur, product_id, files, existing_count):
    slots_left = MAX_PRODUCT_MEDIA - existing_count
    saved = 0
    for f in files:
        if not f or not f.filename:
            continue
        if saved >= slots_left:
            flash(f'Only {MAX_PRODUCT_MEDIA} media items are allowed per product; some files were skipped.', 'error')
            break
        ok, err, safe_name, kind = validate_upload(f, allow_video=True)
        if not ok:
            flash(f'{f.filename}: {err}', 'error')
            continue
        save_upload(f, current_app.config['UPLOAD_FOLDER'], safe_name)
        cur.execute(
            "INSERT INTO ProductMedia (media_id, product_id, media_path, media_type, sort_order, created_at) "
            "VALUES (productmedia_seq.NEXTVAL, :pid, :mp, :mt, :so, SYSDATE)",
            {'pid': product_id, 'mp': f'uploads/{safe_name}', 'mt': kind, 'so': existing_count + saved},
        )
        saved += 1
    return saved


@admin_bp.route('/products/add', methods=['GET', 'POST'])
@admin_required
def add_product():
    cur = get_db().cursor()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_id = request.form.get('category_id')
        description = request.form.get('description', '').strip()
        delivery_time_text = request.form.get('delivery_time_text', '').strip()
        free_delivery = 1 if request.form.get('free_delivery') else 0

        ok, err = validate_required_text(name, 'Product name', min_len=2, max_len=150)
        price = stock = cost_price = None
        if ok:
            ok, err, price = validate_price(request.form.get('price'))
        if ok:
            ok, err, cost_price = validate_cost_price(request.form.get('cost_price'))
        if ok:
            ok, err, stock = validate_stock(request.form.get('stock'))
        if not ok:
            flash(err, 'error')
            return redirect(url_for('admin.add_product'))

        image_path = None
        file = request.files.get('image')
        if file and file.filename:
            img_ok, img_err, safe_name, _kind = validate_upload(file, allow_video=False)
            if not img_ok:
                flash(img_err, 'error')
                return redirect(url_for('admin.add_product'))
            save_upload(file, current_app.config['UPLOAD_FOLDER'], safe_name)
            image_path = f'uploads/{safe_name}'

        cur.execute(
            "INSERT INTO Products (product_id, category_id, name, price, cost_price, stock, description, image_path, "
            "delivery_time_text, free_delivery) "
            "VALUES (products_seq.NEXTVAL, :cid, :n, :p, :cp, :s, :d, :img, :dt, :fd)",
            {'cid': category_id, 'n': name, 'p': price, 'cp': cost_price, 's': stock, 'd': description, 'img': image_path,
             'dt': delivery_time_text or None, 'fd': free_delivery},
        )
        cur.execute("SELECT products_seq.CURRVAL FROM dual")
        new_product_id = cur.fetchone()[0]

        _save_gallery_media(cur, new_product_id, request.files.getlist('media'), 0)

        log_admin_action(cur, current_user_id(), 'product.create', 'Product', new_product_id, f'name={name}')
        get_db().commit()
        flash('Product added successfully.', 'success')
        return redirect(url_for('admin.products'))

    cur.execute("SELECT category_id, category_name FROM Categories ORDER BY category_name")
    categories = cur.fetchall()
    return render_template('admin/add_product.html', categories=categories, max_media=MAX_PRODUCT_MEDIA)


@admin_bp.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def edit_product(product_id):
    cur = get_db().cursor()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_id = request.form.get('category_id')
        description = request.form.get('description', '').strip()
        delivery_time_text = request.form.get('delivery_time_text', '').strip()
        free_delivery = 1 if request.form.get('free_delivery') else 0

        ok, err = validate_required_text(name, 'Product name', min_len=2, max_len=150)
        price = stock = cost_price = None
        if ok:
            ok, err, price = validate_price(request.form.get('price'))
        if ok:
            ok, err, cost_price = validate_cost_price(request.form.get('cost_price'))
        if ok:
            ok, err, stock = validate_stock(request.form.get('stock'))
        if not ok:
            flash(err, 'error')
            return redirect(url_for('admin.edit_product', product_id=product_id))

        cur.execute("SELECT image_path FROM Products WHERE product_id = :pid", {'pid': product_id})
        row = cur.fetchone()
        image_path = row[0] if row else None

        file = request.files.get('image')
        if file and file.filename:
            img_ok, img_err, safe_name, _kind = validate_upload(file, allow_video=False)
            if not img_ok:
                flash(img_err, 'error')
                return redirect(url_for('admin.edit_product', product_id=product_id))
            save_upload(file, current_app.config['UPLOAD_FOLDER'], safe_name)
            image_path = f'uploads/{safe_name}'

        cur.execute(
            "UPDATE Products SET name=:n, category_id=:cid, price=:p, cost_price=:cp, stock=:s, description=:d, image_path=:img, "
            "delivery_time_text=:dt, free_delivery=:fd WHERE product_id=:pid",
            {'n': name, 'cid': category_id, 'p': price, 'cp': cost_price, 's': stock, 'd': description,
             'img': image_path, 'dt': delivery_time_text or None, 'fd': free_delivery, 'pid': product_id},
        )

        cur.execute("SELECT COUNT(*) FROM ProductMedia WHERE product_id = :pid", {'pid': product_id})
        existing_count = cur.fetchone()[0]
        _save_gallery_media(cur, product_id, request.files.getlist('media'), existing_count)

        log_admin_action(cur, current_user_id(), 'product.update', 'Product', product_id, f'name={name}')
        get_db().commit()
        flash('Product updated.', 'success')
        return redirect(url_for('admin.products'))

    cur.execute(
        "SELECT product_id, category_id, name, price, NVL(cost_price, 0), stock, description, image_path, "
        "       delivery_time_text, free_delivery FROM Products WHERE product_id = :pid",
        {'pid': product_id},
    )
    product = cur.fetchone()
    if not product:
        flash('Product not found.', 'error')
        return redirect(url_for('admin.products'))

    cur.execute("SELECT category_id, category_name FROM Categories ORDER BY category_name")
    categories = cur.fetchall()
    cur.execute(
        "SELECT media_id, media_path, media_type FROM ProductMedia WHERE product_id = :pid ORDER BY sort_order",
        {'pid': product_id},
    )
    gallery = cur.fetchall()
    return render_template(
        'admin/edit_product.html', product=product, categories=categories, gallery=gallery,
        max_media=MAX_PRODUCT_MEDIA,
    )


@admin_bp.route('/products/media/<int:media_id>/delete', methods=['POST'])
@admin_required
def delete_product_media(media_id):
    cur = get_db().cursor()
    cur.execute("SELECT product_id FROM ProductMedia WHERE media_id = :m", {'m': media_id})
    row = cur.fetchone()
    product_id = row[0] if row else None
    cur.execute("DELETE FROM ProductMedia WHERE media_id = :m", {'m': media_id})
    log_admin_action(cur, current_user_id(), 'product.media_delete', 'Product', product_id)
    get_db().commit()
    flash('Media removed.', 'success')
    return redirect(url_for('admin.edit_product', product_id=product_id) if product_id else url_for('admin.products'))


@admin_bp.route('/products/delete/<int:product_id>', methods=['POST'])
@admin_required
def delete_product(product_id):
    cur = get_db().cursor()
    try:
        cur.execute("DELETE FROM Cart WHERE product_id = :p", {'p': product_id})
        cur.execute("DELETE FROM Wishlist WHERE product_id = :p", {'p': product_id})
        cur.execute("DELETE FROM ProductMedia WHERE product_id = :p", {'p': product_id})
        cur.execute("DELETE FROM Products WHERE product_id = :p", {'p': product_id})
        log_admin_action(cur, current_user_id(), 'product.delete', 'Product', product_id)
        get_db().commit()
        flash('Product deleted.', 'success')
    except oracledb.IntegrityError:
        get_db().rollback()
        flash('Cannot delete product - it is referenced in existing orders.', 'error')
    return redirect(url_for('admin.products'))


# ── CATEGORIES ───────────────────────────────────────────────────
@admin_bp.route('/categories')
@admin_required
def categories():
    cur = get_db().cursor()
    cur.execute(
        "SELECT c.category_id, c.category_name, "
        "       (SELECT COUNT(*) FROM Products p WHERE p.category_id = c.category_id) AS product_count "
        "FROM Categories c ORDER BY c.category_name"
    )
    return render_template('admin/categories.html', categories=cur.fetchall())


@admin_bp.route('/categories/add', methods=['POST'])
@admin_required
def add_category():
    name = request.form.get('category_name', '').strip()
    ok, err = validate_required_text(name, 'Category name', min_len=2, max_len=100)
    if not ok:
        flash(err, 'error')
        return redirect(url_for('admin.categories'))
    cur = get_db().cursor()
    cur.execute(
        "INSERT INTO Categories (category_id, category_name) VALUES (categories_seq.NEXTVAL, :n)", {'n': name},
    )
    cur.execute("SELECT categories_seq.CURRVAL FROM dual")
    log_admin_action(cur, current_user_id(), 'category.create', 'Category', cur.fetchone()[0], f'name={name}')
    get_db().commit()
    flash('Category added.', 'success')
    return redirect(url_for('admin.categories'))


@admin_bp.route('/categories/delete/<int:category_id>', methods=['POST'])
@admin_required
def delete_category(category_id):
    action = request.form.get('action', 'delete')
    cur = get_db().cursor()
    try:
        if action == 'move':
            # Ensure an "Uncategorized" category exists
            cur.execute("SELECT category_id FROM Categories WHERE LOWER(category_name) = 'uncategorized'")
            row = cur.fetchone()
            if row:
                uncat_id = row[0]
            else:
                cur.execute(
                    "INSERT INTO Categories (category_id, category_name) "
                    "VALUES (categories_seq.NEXTVAL, 'Uncategorized')"
                )
                cur.execute("SELECT categories_seq.CURRVAL FROM dual")
                uncat_id = cur.fetchone()[0]
            # Move products to Uncategorized
            cur.execute(
                "UPDATE Products SET category_id = :ucid WHERE category_id = :cid",
                {'ucid': uncat_id, 'cid': category_id},
            )
            moved = cur.rowcount
            cur.execute("DELETE FROM Categories WHERE category_id = :cid", {'cid': category_id})
            log_admin_action(cur, current_user_id(), 'category.delete', 'Category', category_id,
                             f'{moved} products moved to Uncategorized')
            get_db().commit()
            flash(f'Category deleted. {moved} product(s) moved to Uncategorized.', 'success')

        elif action == 'cascade':
            # Gather product IDs in this category
            cur.execute("SELECT product_id FROM Products WHERE category_id = :cid", {'cid': category_id})
            product_ids = [r[0] for r in cur.fetchall()]

            if product_ids:
                bind = {f'p{i}': pid for i, pid in enumerate(product_ids)}
                ph = ', '.join(f':p{i}' for i in range(len(product_ids)))

                # Delete from every child table that references product_id
                cur.execute(
                    f"DELETE FROM FeedbackReplies WHERE feedback_id IN "
                    f"(SELECT feedback_id FROM ProductFeedback WHERE product_id IN ({ph}))", bind)
                for tbl in ('ProductFeedback', 'ProductMedia', 'CustomerActivityLog',
                            'Cart', 'Wishlist', 'OrderItems'):
                    try:
                        cur.execute(f"DELETE FROM {tbl} WHERE product_id IN ({ph})", bind)
                    except oracledb.DatabaseError:
                        pass  # table may not exist yet
                cur.execute("DELETE FROM Products WHERE category_id = :cid", {'cid': category_id})

            cur.execute("DELETE FROM Categories WHERE category_id = :cid", {'cid': category_id})
            log_admin_action(cur, current_user_id(), 'category.delete', 'Category', category_id,
                             f'Cascade-deleted with {len(product_ids)} products')
            get_db().commit()
            flash(f'Category and {len(product_ids)} product(s) permanently deleted.', 'success')

        else:  # simple delete
            cur.execute("DELETE FROM Categories WHERE category_id = :cid", {'cid': category_id})
            log_admin_action(cur, current_user_id(), 'category.delete', 'Category', category_id)
            get_db().commit()
            flash('Category deleted.', 'success')

    except oracledb.IntegrityError:
        get_db().rollback()
        flash('Cannot delete category — products are still assigned to it.', 'error')
    except Exception as exc:
        get_db().rollback()
        current_app.logger.exception('Error deleting category %s: %s', category_id, exc)
        flash(f'An error occurred while deleting the category: {exc}', 'error')
    return redirect(url_for('admin.categories'))


@admin_bp.route('/categories/<int:category_id>/check')
@admin_required
def category_product_count(category_id):
    cur = get_db().cursor()
    cur.execute("SELECT COUNT(*) FROM Products WHERE category_id = :cid", {'cid': category_id})
    count = cur.fetchone()[0]
    cur.execute("SELECT category_name FROM Categories WHERE category_id = :cid", {'cid': category_id})
    row = cur.fetchone()
    return {'count': count, 'name': row[0] if row else ''}


# ── ORDERS ───────────────────────────────────────────────────────
@admin_bp.route('/orders')
@admin_required
def orders():
    cur = get_db().cursor()
    cur.execute(
        "SELECT o.order_id, u.name, o.order_date, o.total_amount, o.status, o.payment_status "
        "FROM Orders o JOIN Users u ON o.user_id = u.user_id ORDER BY o.order_date DESC"
    )
    return render_template('admin/orders.html', orders=cur.fetchall())


@admin_bp.route('/orders/<int:order_id>')
@admin_required
def order_detail(order_id):
    cur = get_db().cursor()
    cur.execute(
        """
        SELECT o.order_id, u.name, u.email, o.order_date, o.total_amount, o.status,
               o.phone_number, o.delivery_address, o.payment_method, o.payment_status,
               o.payment_proof_path, o.advance_amount, o.coupon_code, o.coupon_discount_amount,
               o.loyalty_points_redeemed, o.loyalty_discount_amount, o.loyalty_points_earned,
               o.cashback_points_awarded, o.payment_rejection_reason
        FROM Orders o JOIN Users u ON o.user_id = u.user_id WHERE o.order_id = :1
        """,
        [order_id],
    )
    order = cur.fetchone()
    if not order:
        flash('Order not found.', 'error')
        return redirect(url_for('admin.orders'))

    try:
        cur.execute(
            "SELECT p.name, oi.quantity, oi.unit_price, NVL(p.cost_price, 0) "
            "FROM OrderItems oi JOIN Products p ON oi.product_id = p.product_id WHERE oi.order_id = :1",
            [order_id],
        )
        raw_items = cur.fetchall()
    except Exception:
        cur.execute(
            "SELECT p.name, oi.quantity, oi.unit_price, 0 "
            "FROM OrderItems oi JOIN Products p ON oi.product_id = p.product_id WHERE oi.order_id = :1",
            [order_id],
        )
        raw_items = cur.fetchall()

    items = []
    total_order_cost = 0.0
    items_subtotal = 0.0
    for name, qty, unit_price, cost_price in raw_items:
        item_total = qty * float(unit_price)
        item_cost = qty * float(cost_price)
        item_profit = item_total - item_cost
        items_subtotal += item_total
        total_order_cost += item_cost
        items.append((name, qty, unit_price, cost_price, item_total, item_cost, item_profit))

    realized_revenue = float(order[4]) if order[4] else 0.0
    coupon_discount = float(order[13]) if order[13] else 0.0
    loyalty_discount = float(order[15]) if order[15] else 0.0
    total_discounts = coupon_discount + loyalty_discount
    net_order_profit = realized_revenue - total_order_cost
    margin_pct = (net_order_profit / realized_revenue * 100) if realized_revenue > 0 else 0.0
    financials = {
        'items_subtotal': items_subtotal,
        'total_cost': total_order_cost,
        'coupon_discount': coupon_discount,
        'loyalty_discount': loyalty_discount,
        'total_discounts': total_discounts,
        'realized_revenue': realized_revenue,
        'net_profit': net_order_profit,
        'margin_pct': margin_pct,
    }

    cur.execute("SELECT amount, payment_date, method FROM Payments WHERE order_id = :1", [order_id])
    payment = cur.fetchone()
    whatsapp_link = _whatsapp_link(order[6], f'Hi {order[1]}, this is SmartCart regarding your order #{order_id}.')
    return render_template(
        'admin/order_detail.html', order=order, items=items, payment=payment,
        financials=financials, whatsapp_link=whatsapp_link,
    )


# ── REVENUE & PROFIT MARGIN CALCULATOR ───────────────────────────
@admin_bp.route('/revenue')
@admin_required
def revenue_dashboard():
    cur = get_db().cursor()
    status_filter = request.args.get('status', 'all').strip().lower()

    # Base order filter (exclude cancelled orders unless explicitly selected)
    params = {}
    if status_filter and status_filter != 'all':
        status_clause = "o.status = :st"
        params['st'] = status_filter
    else:
        status_clause = "o.status != 'cancelled'"

    # 1. High-level financial KPIs
    cur.execute(
        f"""
        SELECT 
            NVL(SUM(o.total_amount), 0) AS total_revenue,
            NVL(SUM(o.coupon_discount_amount), 0) AS total_coupon_disc,
            NVL(SUM(o.loyalty_discount_amount), 0) AS total_loyalty_disc,
            COUNT(*) AS order_count
        FROM Orders o 
        WHERE {status_clause}
        """,
        params,
    )
    rev_row = cur.fetchone()
    total_revenue = float(rev_row[0])
    total_coupon_disc = float(rev_row[1])
    total_loyalty_disc = float(rev_row[2])
    total_discounts = total_coupon_disc + total_loyalty_disc
    order_count = rev_row[3]
    gross_sales = total_revenue + total_discounts

    # Calculate Total Cost of Goods Sold (COGS) for these orders
    total_cogs = 0.0
    try:
        cur.execute(
            f"""
            SELECT NVL(SUM(oi.quantity * NVL(p.cost_price, 0)), 0)
            FROM OrderItems oi
            JOIN Products p ON oi.product_id = p.product_id
            JOIN Orders o ON oi.order_id = o.order_id
            WHERE {status_clause}
            """,
            params,
        )
        total_cogs = float(cur.fetchone()[0])
    except Exception:
        total_cogs = 0.0

    net_profit = total_revenue - total_cogs
    margin_pct = (net_profit / total_revenue * 100) if total_revenue > 0 else 0.0

    # 2. Product-by-product profitability breakdown
    product_stats = []
    try:
        cur.execute(
            f"""
            SELECT 
                p.product_id,
                p.name,
                c.category_name,
                p.price AS sale_price,
                NVL(p.cost_price, 0) AS cost_price,
                (p.price - NVL(p.cost_price, 0)) AS unit_profit,
                CASE WHEN p.price > 0 THEN ((p.price - NVL(p.cost_price, 0)) / p.price * 100) ELSE 0 END AS unit_margin_pct,
                NVL(sales.units_sold, 0) AS units_sold,
                NVL(sales.total_revenue, 0) AS total_product_revenue,
                NVL(sales.total_cost, 0) AS total_product_cost,
                (NVL(sales.total_revenue, 0) - NVL(sales.total_cost, 0)) AS total_product_profit
            FROM Products p
            JOIN Categories c ON p.category_id = c.category_id
            LEFT JOIN (
                SELECT 
                    oi.product_id,
                    SUM(oi.quantity) AS units_sold,
                    SUM(oi.quantity * oi.unit_price) AS total_revenue,
                    SUM(oi.quantity * NVL(p2.cost_price, 0)) AS total_cost
                FROM OrderItems oi
                JOIN Products p2 ON oi.product_id = p2.product_id
                JOIN Orders o ON oi.order_id = o.order_id
                WHERE {status_clause}
                GROUP BY oi.product_id
            ) sales ON p.product_id = sales.product_id
            ORDER BY total_product_profit DESC, units_sold DESC, p.product_id
            """,
            params,
        )
        product_stats = cur.fetchall()
    except Exception as e:
        current_app.logger.warning(f"Fallback product_stats query: {e}")
        cur.execute(
            "SELECT p.product_id, p.name, c.category_name, p.price, 0, p.price, 100, 0, 0, 0, 0 "
            "FROM Products p JOIN Categories c ON p.category_id = c.category_id ORDER BY p.product_id"
        )
        product_stats = cur.fetchall()

    # 3. Order-by-order financial list (up to 50 latest)
    orders_financial = []
    try:
        cur.execute(
            f"""
            SELECT * FROM (
                SELECT 
                    o.order_id,
                    u.name AS customer_name,
                    o.order_date,
                    o.total_amount AS realized_total,
                    (NVL(o.coupon_discount_amount, 0) + NVL(o.loyalty_discount_amount, 0)) AS total_discount,
                    NVL((
                        SELECT SUM(oi.quantity * NVL(p.cost_price, 0))
                        FROM OrderItems oi JOIN Products p ON oi.product_id = p.product_id
                        WHERE oi.order_id = o.order_id
                    ), 0) AS order_cost,
                    o.status
                FROM Orders o
                JOIN Users u ON o.user_id = u.user_id
                WHERE {status_clause}
                ORDER BY o.order_date DESC
            ) WHERE ROWNUM <= 50
            """,
            params,
        )
        order_rows = cur.fetchall()
        for r in order_rows:
            oid, cname, odate, realized, disc, cost, ost = r
            realized_f = float(realized)
            cost_f = float(cost)
            prof_f = realized_f - cost_f
            m_pct = (prof_f / realized_f * 100) if realized_f > 0 else 0.0
            orders_financial.append({
                'order_id': oid,
                'customer_name': cname,
                'order_date': odate,
                'realized_total': realized_f,
                'total_discount': float(disc),
                'order_cost': cost_f,
                'net_profit': prof_f,
                'margin_pct': m_pct,
                'status': ost,
            })
    except Exception as e:
        current_app.logger.warning(f"Fallback order financials query: {e}")

    settings = sitesettings.get_settings(cur)
    min_margin_floor = sitesettings.get_setting_number(settings, 'min_profit_margin_floor', 300)

    summary = {
        'total_revenue': total_revenue,
        'gross_sales': gross_sales,
        'total_cogs': total_cogs,
        'total_coupon_disc': total_coupon_disc,
        'total_loyalty_disc': total_loyalty_disc,
        'total_discounts': total_discounts,
        'net_profit': net_profit,
        'margin_pct': margin_pct,
        'order_count': order_count,
        'min_margin_floor': min_margin_floor,
    }

    return render_template(
        'admin/revenue.html',
        summary=summary,
        product_stats=product_stats,
        orders_financial=orders_financial,
        status_filter=status_filter,
    )


@admin_bp.route('/orders/<int:order_id>/packing-slip')
@admin_required
def packing_slip(order_id):
    cur = get_db().cursor()
    cur.execute(
        """
        SELECT o.order_id, u.name, o.phone_number, o.delivery_address,
               o.address_city, o.address_area, o.address_house_no,
               o.address_block_sector, o.address_landmark, o.address_notes,
               o.total_amount, o.payment_method, o.advance_amount
        FROM Orders o JOIN Users u ON o.user_id = u.user_id WHERE o.order_id = :1
        """,
        [order_id],
    )
    order = cur.fetchone()
    if not order:
        flash('Order not found.', 'error')
        return redirect(url_for('admin.orders'))

    cur.execute(
        "SELECT p.name, oi.quantity, oi.unit_price "
        "FROM OrderItems oi JOIN Products p ON oi.product_id = p.product_id WHERE oi.order_id = :1",
        [order_id],
    )
    items = cur.fetchall()
    return render_template('admin/packing_slip.html', order=order, items=items)


@admin_bp.route('/orders/update_status', methods=['POST'])
@admin_required
def update_order_status():
    order_id = int(request.form['order_id'])
    status = request.form['status']
    allowed = {'pending', 'shipped', 'delivered', 'cancelled'}
    if status not in allowed:
        flash('Invalid status value.', 'error')
        return redirect(url_for('admin.orders'))

    cur = get_db().cursor()
    cur.execute(
        "SELECT status, payment_status FROM Orders WHERE order_id = :oid", {'oid': order_id},
    )
    row = cur.fetchone()
    if not row:
        flash('Order not found.', 'error')
        return redirect(url_for('admin.orders'))
    current_status, payment_status = row

    if status in ('shipped', 'delivered') and payment_status != 'verified':
        flash('Cannot dispatch - payment not yet verified.', 'error')
        return redirect(url_for('admin.order_detail', order_id=order_id))

    cur.execute("UPDATE Orders SET status = :s WHERE order_id = :oid", {'s': status, 'oid': order_id})

    if status == 'cancelled' and current_status != 'cancelled':
        cur.execute(
            "UPDATE Products p SET p.stock = p.stock + ("
            "    SELECT oi.quantity FROM OrderItems oi WHERE oi.product_id = p.product_id AND oi.order_id = :oid"
            ") WHERE p.product_id IN (SELECT product_id FROM OrderItems WHERE order_id = :oid)",
            {'oid': order_id},
        )
        flash('Order cancelled and stock restored.', 'success')
    elif status == 'delivered' and current_status != 'delivered':
        points_var = cur.var(int)
        cur.callproc('complete_order_loyalty', [order_id, points_var])
        flash(f'Order marked delivered. {points_var.getvalue()} loyalty points awarded.', 'success')
    else:
        flash('Order status updated.', 'success')

    log_admin_action(cur, current_user_id(), 'order.status_change', 'Order', order_id,
                      f'{current_status} -> {status}')
    get_db().commit()
    return redirect(url_for('admin.order_detail', order_id=order_id))


# ── PAYMENT VERIFICATION ─────────────────────────────────────────
@admin_bp.route('/payments')
@admin_required
def payment_verification():
    cur = get_db().cursor()
    cur.execute(
        """
        SELECT o.order_id, u.name, u.email, o.phone_number, o.total_amount, o.payment_method,
               o.advance_amount, o.payment_proof_path, o.order_date
        FROM Orders o JOIN Users u ON o.user_id = u.user_id
        WHERE o.payment_status = 'pending_verification'
        ORDER BY o.order_date
        """
    )
    return render_template('admin/payment_verification.html', pending=cur.fetchall())


@admin_bp.route('/payments/<int:order_id>/verify', methods=['POST'])
@admin_required
def verify_payment(order_id):
    cur = get_db().cursor()
    cur.execute(
        "SELECT u.user_id, u.name, u.email, o.total_amount, o.payment_method, o.phone_number "
        "FROM Orders o JOIN Users u ON o.user_id = u.user_id WHERE o.order_id = :1",
        [order_id],
    )
    row = cur.fetchone()
    if not row:
        flash('Order not found.', 'error')
        return redirect(url_for('admin.payment_verification'))
    _user_id, name, email, total_amount, method, phone = row

    cur.execute(
        "UPDATE Orders SET payment_status = 'verified', payment_verified_at = SYSDATE, "
        "payment_verified_by = :p_uid WHERE order_id = :oid",
        {'p_uid': current_user_id(), 'oid': order_id},
    )

    if method == 'bank_transfer':
        settings = sitesettings.get_settings(cur)
        cashback_points = int(sitesettings.get_setting_number(settings, 'cashback_points', 400))
        pts_var = cur.var(int)
        cur.callproc('verify_bank_transfer_cashback', [order_id, cashback_points, pts_var])

    log_admin_action(cur, current_user_id(), 'payment.verify', 'Order', order_id)
    get_db().commit()

    send_payment_verified_email(email, name, order_id, total_amount)
    whatsapp_link = _whatsapp_link(
        phone, f'Hi {name}, your SmartCart payment for order #{order_id} has been verified. '
               f'Your order will be dispatched soon. Thank you!',
    )
    flash('Payment verified. Confirmation email sent.', 'success')
    return redirect(url_for('admin.order_detail', order_id=order_id) + f'?whatsapp={quote(whatsapp_link)}')


@admin_bp.route('/payments/<int:order_id>/reject', methods=['POST'])
@admin_required
def reject_payment(order_id):
    reason = request.form.get('reason', '').strip() or 'Payment proof could not be verified.'
    cur = get_db().cursor()
    cur.execute(
        "UPDATE Orders SET payment_status = 'rejected', payment_rejection_reason = :r WHERE order_id = :oid",
        {'r': reason, 'oid': order_id},
    )
    log_admin_action(cur, current_user_id(), 'payment.reject', 'Order', order_id, reason)
    get_db().commit()
    flash('Payment rejected.', 'success')
    return redirect(url_for('admin.order_detail', order_id=order_id))


# ── COUPONS ──────────────────────────────────────────────────────
@admin_bp.route('/coupons')
@admin_required
def coupons():
    cur = get_db().cursor()
    cur.execute(
        "SELECT coupon_id, code, discount_percent, max_uses, used_count, valid_from, valid_to, active "
        "FROM Coupons ORDER BY created_at DESC"
    )
    return render_template('admin/coupons.html', coupons=cur.fetchall())


@admin_bp.route('/coupons/add', methods=['POST'])
@admin_required
def add_coupon():
    code = request.form.get('code', '').strip().upper()
    ok, err = validate_required_text(code, 'Coupon code', min_len=3, max_len=30)
    pct = None
    if ok:
        ok, err, pct = validate_discount_percent(request.form.get('discount_percent'))
    if not ok:
        flash(err, 'error')
        return redirect(url_for('admin.coupons'))

    max_uses = request.form.get('max_uses') or None
    valid_to = request.form.get('valid_to') or None

    cur = get_db().cursor()
    try:
        cur.execute(
            "INSERT INTO Coupons (coupon_id, code, discount_percent, max_uses, valid_to, created_by) "
            "VALUES (coupons_seq.NEXTVAL, :c, :p, :m, TO_DATE(:vt, 'YYYY-MM-DD'), :u)",
            {'c': code, 'p': pct, 'm': max_uses, 'vt': valid_to, 'u': current_user_id()},
        )
        log_admin_action(cur, current_user_id(), 'coupon.create', 'Coupon', None, f'code={code}')
        get_db().commit()
        flash('Coupon created.', 'success')
    except oracledb.IntegrityError:
        get_db().rollback()
        flash('That coupon code already exists.', 'error')
    return redirect(url_for('admin.coupons'))


@admin_bp.route('/coupons/<int:coupon_id>/toggle', methods=['POST'])
@admin_required
def toggle_coupon(coupon_id):
    cur = get_db().cursor()
    cur.execute("SELECT active FROM Coupons WHERE coupon_id = :c", {'c': coupon_id})
    row = cur.fetchone()
    if not row:
        flash('Coupon not found.', 'error')
        return redirect(url_for('admin.coupons'))
    new_state = 0 if row[0] else 1
    cur.execute("UPDATE Coupons SET active = :a WHERE coupon_id = :c", {'a': new_state, 'c': coupon_id})
    log_admin_action(cur, current_user_id(), 'coupon.toggle', 'Coupon', coupon_id, f'active={new_state}')
    get_db().commit()
    flash('Coupon updated.', 'success')
    return redirect(url_for('admin.coupons'))


# ── SITE SETTINGS ────────────────────────────────────────────────
@admin_bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def site_settings():
    cur = get_db().cursor()
    all_keys = [key for _group, fields in sitesettings.FIELD_GROUPS for key, _label, _kind in fields]

    if request.method == 'POST':
        for key in all_keys:
            value = request.form.get(key, '').strip()
            cur.execute(
                """
                MERGE INTO SiteSettings s
                USING (SELECT :k AS setting_key FROM dual) d
                ON (s.setting_key = d.setting_key)
                WHEN MATCHED THEN UPDATE SET s.setting_value = :v
                WHEN NOT MATCHED THEN INSERT (setting_key, setting_value) VALUES (:k, :v)
                """,
                {'k': key, 'v': value},
            )
        log_admin_action(cur, current_user_id(), 'settings.update')
        get_db().commit()
        flash('Settings updated.', 'success')
        return redirect(url_for('admin.site_settings'))

    settings = sitesettings.get_settings(cur)
    return render_template(
        'admin/site_settings.html', settings=settings, field_groups=sitesettings.FIELD_GROUPS,
    )


# ── USERS / INVENTORY / AUDIT LOG ────────────────────────────────
@admin_bp.route('/users')
@admin_required
def users():
    cur = get_db().cursor()
    cur.execute(
        "SELECT user_id, name, email, role, created_at, loyalty_points_balance, email_verified "
        "FROM Users ORDER BY created_at DESC"
    )
    return render_template('admin/users.html', users=cur.fetchall())


@admin_bp.route('/users/<int:user_id>/verify', methods=['POST'])
@admin_required
def verify_user_email(user_id):
    cur = get_db().cursor()
    cur.execute(
        "UPDATE Users SET email_verified = 1, verification_code = NULL, "
        "verification_code_expires = NULL WHERE user_id = :v_user_id",
        {'v_user_id': user_id},
    )
    log_admin_action(cur, current_user_id(), 'user.manual_verify', 'User', user_id,
                      'Verified manually (e.g. after an email delivery failure)')
    get_db().commit()
    flash('Account verified. The customer can now log in.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/inventory')
@admin_required
def inventory():
    cur = get_db().cursor()
    cur.execute("SELECT * FROM AdminInventoryView ORDER BY product_id")
    return render_template('admin/inventory.html', inventory=cur.fetchall())


@admin_bp.route('/audit-log')
@admin_required
def audit_log():
    cur = get_db().cursor()
    action_filter = request.args.get('action', '').strip()
    inner_query = (
        "SELECT al.audit_id, u.name, al.action, al.target_type, al.target_id, al.details, "
        "al.ip_address, al.created_at "
        "FROM AdminAuditLog al JOIN Users u ON al.admin_user_id = u.user_id WHERE 1=1"
    )
    params = {}
    if action_filter:
        inner_query += " AND al.action = :act"
        params['act'] = action_filter
    inner_query += " ORDER BY al.created_at DESC"
    query = f"SELECT * FROM ({inner_query}) WHERE ROWNUM <= 100"
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.execute("SELECT DISTINCT action FROM AdminAuditLog ORDER BY action")
    actions = [r[0] for r in cur.fetchall()]
    return render_template('admin/audit_log.html', rows=rows, actions=actions, selected_action=action_filter)
