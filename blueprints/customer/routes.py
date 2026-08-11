import os

import oracledb
from flask import (Blueprint, current_app, flash, redirect, render_template,
                    request, session, url_for)

import sitesettings
from activity import log_activity
from blueprints.auth.decorators import login_required
from db import get_db
from uploads import save_upload, validate_upload
from validators import validate_phone_pk, validate_required_text

customer_bp = Blueprint('customer', __name__)


# ── PUBLIC CATALOG ──────────────────────────────────────────────
@customer_bp.route('/')
def index():
    category_id = request.args.get('category_id')
    search = request.args.get('search', '').strip()

    cur = get_db().cursor()
    query = (
        "SELECT p.product_id, p.name, p.price, p.stock, p.description, "
        "p.image_path, c.category_name, p.delivery_time_text, p.free_delivery "
        "FROM Products p JOIN Categories c ON p.category_id = c.category_id "
        "WHERE 1=1"
    )
    params = {}
    if category_id:
        query += " AND p.category_id = :cid"
        params['cid'] = int(category_id)
    if search:
        query += " AND LOWER(p.name) LIKE :s"
        params['s'] = f'%{search.lower()}%'
    cur.execute(query, params)
    products = cur.fetchall()

    cur.execute("SELECT category_id, category_name FROM Categories ORDER BY category_name")
    categories = cur.fetchall()

    return render_template(
        'customer/home.html', products=products, categories=categories,
        selected_category=category_id, search=search,
    )


@customer_bp.route('/product/<int:product_id>')
def product_detail(product_id):
    cur = get_db().cursor()
    cur.execute(
        "SELECT p.product_id, p.name, p.price, p.stock, p.description, "
        "p.image_path, c.category_name, p.delivery_time_text, p.free_delivery "
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
        log_activity(cur, session['user_id'], 'view_product', product_id=product_id)
        get_db().commit()

    return render_template(
        'customer/product_detail.html', product=product, gallery=gallery, feedback_list=feedback_list,
    )


# ── CART ─────────────────────────────────────────────────────────
@customer_bp.route('/cart')
@login_required
def view_cart():
    cur = get_db().cursor()
    cur.execute(
        "SELECT c.cart_id, p.product_id, p.name, p.price, c.quantity, p.image_path "
        "FROM Cart c JOIN Products p ON c.product_id = p.product_id "
        "WHERE c.user_id = :1",
        [session['user_id']],
    )
    items = cur.fetchall()
    total = sum(row[3] * row[4] for row in items)
    return render_template('customer/cart.html', items=items, total=total)


@customer_bp.route('/cart/add', methods=['POST'])
@login_required
def add_to_cart():
    product_id = int(request.form['product_id'])
    quantity = int(request.form.get('quantity', 1))

    cur = get_db().cursor()
    cur.execute(
        "SELECT cart_id FROM Cart WHERE user_id = :1 AND product_id = :2",
        [session['user_id'], product_id],
    )
    existing = cur.fetchone()

    if existing:
        cur.execute(
            "UPDATE Cart SET quantity = quantity + :1 WHERE cart_id = :2",
            [quantity, existing[0]],
        )
    else:
        cur.execute(
            "INSERT INTO Cart (cart_id, user_id, product_id, quantity) "
            "VALUES (cart_seq.NEXTVAL, :1, :2, :3)",
            [session['user_id'], product_id, quantity],
        )
    log_activity(cur, session['user_id'], 'add_to_cart', product_id=product_id)
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
            [cart_id, session['user_id']],
        )
    else:
        cur.execute(
            "UPDATE Cart SET quantity = :1 WHERE cart_id = :2 AND user_id = :3",
            [quantity, cart_id, session['user_id']],
        )
    get_db().commit()
    return redirect(url_for('customer.view_cart'))


@customer_bp.route('/cart/remove/<int:cart_id>', methods=['POST'])
@login_required
def remove_from_cart(cart_id):
    cur = get_db().cursor()
    cur.execute(
        "DELETE FROM Cart WHERE cart_id = :1 AND user_id = :2",
        [cart_id, session['user_id']],
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
        [session['user_id']],
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
        [session['user_id'], product_id],
    )
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO Wishlist (wishlist_id, user_id, product_id) "
            "VALUES (wishlist_seq.NEXTVAL, :1, :2)",
            [session['user_id'], product_id],
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
        [wishlist_id, session['user_id']],
    )
    get_db().commit()
    return redirect(url_for('customer.view_wishlist'))


# ── CHECKOUT / ORDERS ────────────────────────────────────────────
@customer_bp.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cur = get_db().cursor()
    cur.execute("SELECT loyalty_points_balance FROM Users WHERE user_id = :1", [session['user_id']])
    points_balance = cur.fetchone()[0]

    if request.method == 'POST':
        payment_method = request.form.get('payment_method', 'cod')
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        coupon_code = request.form.get('coupon_code', '').strip() or None
        try:
            points_to_redeem = int(request.form.get('points_to_redeem', 0) or 0)
        except ValueError:
            points_to_redeem = 0

        ok, err = validate_required_text(address, 'Delivery address', min_len=8, max_len=255)
        if ok:
            ok, err = validate_phone_pk(phone)
        if payment_method not in ('cod', 'bank_transfer'):
            ok, err = False, 'Invalid payment method.'
        if not ok:
            flash(err, 'error')
            return redirect(url_for('customer.checkout'))

        cur.execute("SELECT COUNT(*) FROM Cart WHERE user_id = :1", [session['user_id']])
        if cur.fetchone()[0] == 0:
            flash('Your cart is empty.', 'error')
            return redirect(url_for('customer.view_cart'))

        proof_file = request.files.get('payment_proof')
        if not proof_file or not proof_file.filename:
            flash('Please upload a screenshot of your bank transfer as payment proof.', 'error')
            return redirect(url_for('customer.checkout'))
        proof_ok, proof_err, safe_name, _kind = validate_upload(proof_file, allow_video=False)
        if not proof_ok:
            flash(proof_err, 'error')
            return redirect(url_for('customer.checkout'))
        save_upload(proof_file, current_app.config['PAYMENT_PROOF_UPLOAD_FOLDER'], safe_name)
        proof_path = f'uploads/payment_proofs/{safe_name}'

        log_activity(cur, session['user_id'], 'payment_uploaded')
        get_db().commit()

        order_id_var = cur.var(int)
        final_total_var = cur.var(float)
        coupon_disc_var = cur.var(float)
        loyalty_disc_var = cur.var(float)
        points_redeemed_var = cur.var(int)
        advance_var = cur.var(float)

        settings = sitesettings.get_settings(cur)
        cod_advance_amount = sitesettings.get_setting_number(settings, 'cod_advance_amount', 300)

        try:
            cur.callproc('place_order', [
                session['user_id'], payment_method, address, phone, proof_path,
                points_to_redeem, coupon_code, cod_advance_amount,
                order_id_var, final_total_var, coupon_disc_var, loyalty_disc_var,
                points_redeemed_var, advance_var,
            ])
            get_db().commit()

            new_order_id = order_id_var.getvalue()
            log_activity(cur, session['user_id'], 'order_placed', order_id=new_order_id)
            get_db().commit()

            msg = f'Order #{new_order_id} placed! Advance required: Rs. {advance_var.getvalue():.2f}.'
            if points_redeemed_var.getvalue():
                msg += f' {points_redeemed_var.getvalue()} loyalty points redeemed.'
            if coupon_disc_var.getvalue():
                msg += f' Coupon saved you Rs. {coupon_disc_var.getvalue():.2f}.'
            flash(msg, 'success')
            return redirect(url_for('customer.order_detail', order_id=new_order_id))

        except oracledb.DatabaseError as e:
            error_msg = str(e)
            if 'ORA-20001' in error_msg:
                flash(error_msg.split('ORA-20001:')[-1].strip(), 'error')
            elif 'ORA-20002' in error_msg:
                flash('Your cart is empty.', 'error')
            elif 'ORA-20003' in error_msg:
                flash('Invalid or expired coupon code.', 'error')
            else:
                flash('Order could not be placed. Please try again.', 'error')
            return redirect(url_for('customer.view_cart'))

    # GET
    log_activity(cur, session['user_id'], 'checkout_start')
    get_db().commit()

    cur.execute(
        "SELECT p.name, c.quantity, p.price FROM Cart c JOIN Products p ON c.product_id = p.product_id "
        "WHERE c.user_id = :1",
        [session['user_id']],
    )
    cart_items = cur.fetchall()
    subtotal = sum(row[1] * row[2] for row in cart_items)
    max_redeemable_points = int(min(points_balance, subtotal * 0.5 * 2))
    settings = sitesettings.get_settings(cur)
    return render_template(
        'customer/checkout.html', cart_items=cart_items, subtotal=subtotal,
        points_balance=points_balance, max_redeemable_points=max_redeemable_points,
        settings=settings,
    )


@customer_bp.route('/orders')
@login_required
def order_history():
    cur = get_db().cursor()
    cur.execute(
        "SELECT order_id, order_date, total_amount, status, payment_status "
        "FROM Orders WHERE user_id = :1 ORDER BY order_date DESC",
        [session['user_id']],
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
        [order_id, session['user_id']],
    )
    order = cur.fetchone()
    if not order:
        flash('Order not found.', 'error')
        return redirect(url_for('customer.order_history'))

    cur.execute(
        "SELECT p.name, oi.quantity, oi.unit_price "
        "FROM OrderItems oi JOIN Products p ON oi.product_id = p.product_id "
        "WHERE oi.order_id = :1",
        [order_id],
    )
    items = cur.fetchall()

    cur.execute("SELECT amount, payment_date, method FROM Payments WHERE order_id = :1", [order_id])
    payment = cur.fetchone()
    return render_template('customer/order_detail.html', order=order, items=items, payment=payment)


# ── PROFILE ──────────────────────────────────────────────────────
@customer_bp.route('/account/profile')
@login_required
def profile():
    cur = get_db().cursor()
    cur.execute(
        "SELECT name, email, role, created_at, loyalty_points_balance FROM Users WHERE user_id = :1",
        [session['user_id']],
    )
    user = cur.fetchone()

    cur.execute("SELECT COUNT(*) FROM Orders WHERE user_id = :1", [session['user_id']])
    order_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM Wishlist WHERE user_id = :1", [session['user_id']])
    wishlist_count = cur.fetchone()[0]

    # Oracle 11.2 doesn't support FETCH FIRST N ROWS ONLY, so use a ROWNUM subquery.
    cur.execute(
        """
        SELECT * FROM (
            SELECT ledger_id, order_id, entry_type, points, rupee_value, balance_after, created_at
            FROM LoyaltyLedger WHERE user_id = :1 ORDER BY created_at DESC
        ) WHERE ROWNUM <= 5
        """,
        [session['user_id']],
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
    cur.execute("SELECT loyalty_points_balance FROM Users WHERE user_id = :1", [session['user_id']])
    balance = cur.fetchone()[0]
    cur.execute(
        """
        SELECT ledger_id, order_id, entry_type, points, rupee_value, balance_after, created_at
        FROM LoyaltyLedger WHERE user_id = :1 ORDER BY created_at DESC
        """,
        [session['user_id']],
    )
    ledger = cur.fetchall()
    return render_template('customer/loyalty_history.html', balance=balance, ledger=ledger)
