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
from cache_service import (invalidate_banners, invalidate_brands,
                           invalidate_categories, invalidate_site_settings)
from db import get_db
from extensions import limiter
from security import log_admin_action
from uploads import convert_image_to_base64, process_upload, save_upload, validate_upload
from validators import (validate_cost_price, validate_coupon_discount,
                         validate_discount_percent, validate_price,
                         validate_required_text, validate_stock)

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


from whatsapp_utils import format_whatsapp_phone, get_whatsapp_order_link


def _whatsapp_link(phone, message):
    phone_clean = format_whatsapp_phone(phone)
    if not phone_clean:
        return '#'
    return f'https://api.whatsapp.com/send?phone={phone_clean}&text={quote(message)}'



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

    # Confirmed Net Profit: only orders where payment was physically received
    # (COD with cash_received_at set, OR bank_transfer with payment_status=verified)
    confirmed_revenue = 0.0
    confirmed_cost = 0.0
    confirmed_orders_count = 0
    try:
        cur.execute("""
            SELECT NVL(SUM(o.total_amount), 0), COUNT(o.order_id)
            FROM Orders o
            WHERE o.status != 'cancelled'
              AND (
                  (o.payment_method = 'cod' AND o.cash_received_at IS NOT NULL)
                  OR (o.payment_method = 'bank_transfer' AND o.payment_status = 'verified')
              )
        """)
        row = cur.fetchone()
        confirmed_revenue = float(row[0])
        confirmed_orders_count = int(row[1])
        cur.execute("""
            SELECT NVL(SUM(oi.quantity * NVL(p.cost_price, 0)), 0)
            FROM OrderItems oi
            JOIN Products p ON oi.product_id = p.product_id
            JOIN Orders o ON oi.order_id = o.order_id
            WHERE o.status != 'cancelled'
              AND (
                  (o.payment_method = 'cod' AND o.cash_received_at IS NOT NULL)
                  OR (o.payment_method = 'bank_transfer' AND o.payment_status = 'verified')
              )
        """)
        confirmed_cost = float(cur.fetchone()[0])
    except Exception as e:
        current_app.logger.warning(f"Error computing confirmed profit: {e}")

    confirmed_net_profit = confirmed_revenue - confirmed_cost
    confirmed_margin = (confirmed_net_profit / confirmed_revenue * 100) if confirmed_revenue > 0 else 0.0

    cur.execute("SELECT COUNT(*) FROM Orders WHERE payment_status = 'pending_verification'")
    pending_payments = cur.fetchone()[0]

    # Orders awaiting cash collection (COD delivered but cash not yet marked received)
    pending_cod_collection = 0
    try:
        cur.execute("""
            SELECT COUNT(*) FROM Orders
            WHERE payment_method = 'cod'
              AND status = 'delivered'
              AND cash_received_at IS NULL
        """)
        pending_cod_collection = cur.fetchone()[0]
    except Exception:
        pass

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
        confirmed_net_profit=confirmed_net_profit, confirmed_margin=confirmed_margin,
        confirmed_revenue=confirmed_revenue, confirmed_orders_count=confirmed_orders_count,
        pending_payments=pending_payments, pending_cod_collection=pending_cod_collection,
        recent_orders=recent_orders,
    )



# ── PRODUCTS ─────────────────────────────────────────────────────
@admin_bp.route('/products')
@admin_required
def products():
    cur = get_db().cursor()
    try:
        cur.execute(
            "SELECT p.product_id, p.name, c.category_name, p.price, NVL(p.cost_price, 0), p.stock, p.image_path, b.brand_name "
            "FROM Products p JOIN Categories c ON p.category_id = c.category_id "
            "LEFT JOIN Brands b ON p.brand_id = b.brand_id "
            "ORDER BY p.product_id"
        )
        rows = cur.fetchall()
    except Exception as e:
        current_app.logger.warning(f"Fallback products query: {e}")
        cur.execute(
            "SELECT p.product_id, p.name, c.category_name, p.price, 0, p.stock, p.image_path, NULL "
            "FROM Products p JOIN Categories c ON p.category_id = c.category_id "
            "ORDER BY p.product_id"
        )
        rows = cur.fetchall()

    upload_dir = current_app.config['UPLOAD_FOLDER']
    product_rows = []
    for r in rows:
        pid, name, cat_name, price, cost_price, stock, img_path, brand_name = r
        if not img_path:
            image_missing = False
        elif isinstance(img_path, str) and (img_path.startswith('data:') or img_path.startswith('http://') or img_path.startswith('https://')):
            image_missing = False
        else:
            image_missing = not os.path.exists(os.path.join(upload_dir, os.path.basename(str(img_path))))
        unit_profit = float(price) - float(cost_price)
        margin_pct = (unit_profit / float(price) * 100) if float(price) > 0 else 0.0
        product_rows.append((pid, name, cat_name, price, cost_price, stock, img_path, image_missing, unit_profit, margin_pct, brand_name))
    return render_template('admin/products.html', products=product_rows)


def _save_gallery_media(cur, product_id, files, existing_count, base64_media_list=None):
    slots_left = MAX_PRODUCT_MEDIA - existing_count
    saved = 0

    if base64_media_list:
        for b64 in base64_media_list:
            if not b64 or not b64.startswith('data:'):
                continue
            if saved >= slots_left:
                break
            kind = 'video' if b64.startswith('data:video/') else 'image'
            try:
                cur.execute(
                    "INSERT INTO ProductMedia (media_id, product_id, media_path, media_type, sort_order, created_at) "
                    "VALUES (productmedia_seq.NEXTVAL, :pid, :mp, :mt, :so, SYSDATE)",
                    {'pid': product_id, 'mp': b64, 'mt': kind, 'so': existing_count + saved},
                )
                saved += 1
            except Exception as e:
                current_app.logger.warning(f"Error saving base64 gallery media for product #{product_id}: {e}")

    if files:
        for f in files:
            if not f or not f.filename:
                continue
            if saved >= slots_left:
                flash(f'Only {MAX_PRODUCT_MEDIA} media items are allowed per product; some files were skipped.', 'error')
                break
            ok, err, media_data, kind = process_upload(f, allow_video=True)
            if not ok:
                flash(f'{f.filename}: {err}', 'error')
                continue
            try:
                cur.execute(
                    "INSERT INTO ProductMedia (media_id, product_id, media_path, media_type, sort_order, created_at) "
                    "VALUES (productmedia_seq.NEXTVAL, :pid, :mp, :mt, :so, SYSDATE)",
                    {'pid': product_id, 'mp': media_data, 'mt': kind, 'so': existing_count + saved},
                )
                saved += 1
            except Exception as e:
                current_app.logger.warning(f"Error saving file gallery media for product #{product_id}: {e}")
    return saved


def _save_product_colors(cur, product_id, form, files):
    color_names = form.getlist('color_name')
    color_codes = form.getlist('color_code')
    color_stocks = form.getlist('color_stock')
    color_b64s = form.getlist('color_image_base64')
    color_files = files.getlist('color_image')

    for i, cname in enumerate(color_names):
        cname = (cname or '').strip()
        if not cname:
            continue
        ccode = color_codes[i].strip() if i < len(color_codes) and color_codes[i] else '#000000'
        try:
            cstock = int(color_stocks[i]) if i < len(color_stocks) and color_stocks[i] else 0
        except ValueError:
            cstock = 0

        cimg = None
        if i < len(color_b64s) and color_b64s[i] and color_b64s[i].startswith('data:image/'):
            cimg = color_b64s[i]
        elif i < len(color_files) and color_files[i] and color_files[i].filename:
            ok, err, data_url, _kind = process_upload(color_files[i], allow_video=False)
            if ok:
                cimg = data_url

        try:
            cur.execute(
                "INSERT INTO ProductColors (color_id, product_id, color_name, color_code, image_path, stock, sort_order, created_at) "
                "VALUES (productcolors_seq.NEXTVAL, :pid, :cn, :cc, :img, :stk, :so, SYSDATE)",
                {'pid': product_id, 'cn': cname, 'cc': ccode, 'img': cimg, 'stk': cstock, 'so': i},
            )
        except Exception as e:
            current_app.logger.warning(f"Error inserting color variant {cname} for product #{product_id}: {e}")


@admin_bp.route('/products/color/<int:color_id>/delete', methods=['POST'])
@admin_required
def delete_product_color(color_id):
    cur = get_db().cursor()
    cur.execute("SELECT product_id FROM ProductColors WHERE color_id = :c", {'c': color_id})
    row = cur.fetchone()
    product_id = row[0] if row else None
    cur.execute("DELETE FROM ProductColors WHERE color_id = :c", {'c': color_id})
    log_admin_action(cur, current_user_id(), 'product.color_delete', 'Product', product_id, f'color_id={color_id}')
    get_db().commit()
    flash('Color variant removed.', 'success')
    return redirect(url_for('admin.edit_product', product_id=product_id) if product_id else url_for('admin.products'))


@admin_bp.route('/products/add', methods=['GET', 'POST'])
@admin_required
def add_product():
    cur = get_db().cursor()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_id = request.form.get('category_id')
        brand_id = request.form.get('brand_id')
        description = request.form.get('description', '').strip()
        delivery_time_text = request.form.get('delivery_time_text', '').strip()
        free_delivery = 1 if request.form.get('free_delivery') else 0
        technical_specs = request.form.get('technical_specs', '').strip()
        highlights = request.form.get('highlights', '').strip()
        box_contents = request.form.get('box_contents', '').strip()

        ok, err = validate_required_text(name, 'Product name', min_len=2, max_len=150)
        if not ok:
            flash(err, 'error')
            return redirect(url_for('admin.add_product'))

        if not category_id:
            flash('Please select a category.', 'error')
            return redirect(url_for('admin.add_product'))
        try:
            category_id = int(category_id)
        except (ValueError, TypeError):
            flash('Invalid category selected.', 'error')
            return redirect(url_for('admin.add_product'))

        try:
            brand_id = int(brand_id) if brand_id and str(brand_id).strip() else None
        except (ValueError, TypeError):
            brand_id = None

        price = stock = cost_price = None
        ok, err, price = validate_price(request.form.get('price'))
        if not ok:
            flash(err, 'error')
            return redirect(url_for('admin.add_product'))

        ok, err, cost_price = validate_cost_price(request.form.get('cost_price'))
        if not ok:
            flash(err, 'error')
            return redirect(url_for('admin.add_product'))

        ok, err, stock = validate_stock(request.form.get('stock'))
        if not ok:
            flash(err, 'error')
            return redirect(url_for('admin.add_product'))

        image_path = None
        image_base64 = request.form.get('image_base64', '').strip()
        if image_base64.startswith('data:image/'):
            image_path = image_base64
        else:
            file = request.files.get('image')
            if file and file.filename:
                img_ok, img_err, data_url, _kind = process_upload(file, allow_video=False)
                if not img_ok:
                    flash(img_err, 'error')
                    return redirect(url_for('admin.add_product'))
                image_path = data_url

        try:
            new_pid_var = cur.var(oracledb.NUMBER)
            try:
                cur.execute(
                    "INSERT INTO Products (product_id, category_id, brand_id, name, price, cost_price, stock, description, image_path, "
                    "delivery_time_text, free_delivery, technical_specs, highlights, box_contents) "
                    "VALUES (products_seq.NEXTVAL, :cid, :bid, :n, :p, :cp, :s, :d, :img, :dt, :fd, :ts, :hl, :bc) "
                    "RETURNING product_id INTO :new_pid",
                    {'cid': category_id, 'bid': brand_id, 'n': name, 'p': price, 'cp': cost_price, 's': stock, 'd': description,
                     'img': image_path, 'dt': delivery_time_text or None, 'fd': free_delivery,
                     'ts': technical_specs or None, 'hl': highlights or None, 'bc': box_contents or None,
                     'new_pid': new_pid_var},
                )
                new_product_id = int(new_pid_var.getvalue()[0])
            except Exception as insert_err:
                current_app.logger.warning(f"Retrying insert with fallback: {insert_err}")
                try:
                    cur.execute(
                        "INSERT INTO Products (product_id, category_id, brand_id, name, price, cost_price, stock, description, image_path, delivery_time_text, free_delivery) "
                        "VALUES (products_seq.NEXTVAL, :cid, :bid, :n, :p, :cp, :s, :d, :img, :dt, :fd) "
                        "RETURNING product_id INTO :new_pid",
                        {'cid': category_id, 'bid': brand_id, 'n': name, 'p': price, 'cp': cost_price, 's': stock, 'd': description,
                         'img': image_path, 'dt': delivery_time_text or None, 'fd': free_delivery, 'new_pid': new_pid_var},
                    )
                    new_product_id = int(new_pid_var.getvalue()[0])
                except Exception:
                    cur.execute(
                        "INSERT INTO Products (product_id, category_id, name, price, cost_price, stock, description, image_path) "
                        "VALUES (products_seq.NEXTVAL, :cid, :n, :p, :cp, :s, :d, :img)",
                        {'cid': category_id, 'n': name, 'p': price, 'cp': cost_price, 's': stock, 'd': description, 'img': image_path},
                    )
                    cur.execute("SELECT products_seq.CURRVAL FROM dual")
                    new_product_id = cur.fetchone()[0]

            gallery_b64 = request.form.getlist('gallery_base64')
            _save_gallery_media(cur, new_product_id, request.files.getlist('media'), 0, base64_media_list=gallery_b64)

            # Save Color Variants
            _save_product_colors(cur, new_product_id, request.form, request.files)

            log_admin_action(cur, current_user_id(), 'product.create', 'Product', new_product_id, f'name={name}')
            get_db().commit()
            flash(f'Product "{name}" added successfully.', 'success')
            return redirect(url_for('admin.products'))
        except Exception as e:
            get_db().rollback()
            current_app.logger.exception(f'Error adding product: {e}')
            flash(f'Failed to add product: {str(e)}', 'error')
            return redirect(url_for('admin.add_product'))

    cur.execute("SELECT category_id, category_name FROM Categories ORDER BY category_name")
    categories = cur.fetchall()
    try:
        cur.execute("SELECT brand_id, brand_name FROM Brands WHERE is_active = 1 ORDER BY brand_name")
        brands = cur.fetchall()
    except Exception:
        brands = []
    return render_template('admin/add_product.html', categories=categories, brands=brands, max_media=MAX_PRODUCT_MEDIA)


@admin_bp.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def edit_product(product_id):
    cur = get_db().cursor()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_id = request.form.get('category_id')
        brand_id = request.form.get('brand_id')
        description = request.form.get('description', '').strip()
        delivery_time_text = request.form.get('delivery_time_text', '').strip()
        free_delivery = 1 if request.form.get('free_delivery') else 0
        technical_specs = request.form.get('technical_specs', '').strip()
        highlights = request.form.get('highlights', '').strip()
        box_contents = request.form.get('box_contents', '').strip()

        ok, err = validate_required_text(name, 'Product name', min_len=2, max_len=150)
        if not ok:
            flash(err, 'error')
            return redirect(url_for('admin.edit_product', product_id=product_id))

        if not category_id:
            flash('Please select a category.', 'error')
            return redirect(url_for('admin.edit_product', product_id=product_id))
        try:
            category_id = int(category_id)
        except (ValueError, TypeError):
            flash('Invalid category selected.', 'error')
            return redirect(url_for('admin.edit_product', product_id=product_id))

        try:
            brand_id = int(brand_id) if brand_id and str(brand_id).strip() else None
        except (ValueError, TypeError):
            brand_id = None

        price = stock = cost_price = None
        ok, err, price = validate_price(request.form.get('price'))
        if not ok:
            flash(err, 'error')
            return redirect(url_for('admin.edit_product', product_id=product_id))

        ok, err, cost_price = validate_cost_price(request.form.get('cost_price'))
        if not ok:
            flash(err, 'error')
            return redirect(url_for('admin.edit_product', product_id=product_id))

        ok, err, stock = validate_stock(request.form.get('stock'))
        if not ok:
            flash(err, 'error')
            return redirect(url_for('admin.edit_product', product_id=product_id))

        cur.execute("SELECT image_path FROM Products WHERE product_id = :pid", {'pid': product_id})
        row = cur.fetchone()
        image_path = row[0] if row else None

        if request.form.get('remove_image') == '1':
            image_path = None

        image_base64 = request.form.get('image_base64', '').strip()
        if image_base64.startswith('data:image/'):
            image_path = image_base64
        else:
            file = request.files.get('image')
            if file and file.filename:
                img_ok, img_err, data_url, _kind = process_upload(file, allow_video=False)
                if not img_ok:
                    flash(img_err, 'error')
                    return redirect(url_for('admin.edit_product', product_id=product_id))
                image_path = data_url

        try:
            try:
                cur.execute(
                    "UPDATE Products SET name=:n, category_id=:cid, brand_id=:bid, price=:p, cost_price=:cp, stock=:s, description=:d, image_path=:img, "
                    "delivery_time_text=:dt, free_delivery=:fd, technical_specs=:ts, highlights=:hl, box_contents=:bc WHERE product_id=:pid",
                    {'n': name, 'cid': category_id, 'bid': brand_id, 'p': price, 'cp': cost_price, 's': stock, 'd': description,
                     'img': image_path, 'dt': delivery_time_text or None, 'fd': free_delivery,
                     'ts': technical_specs or None, 'hl': highlights or None, 'bc': box_contents or None,
                     'pid': product_id},
                )
            except Exception as update_err:
                current_app.logger.warning(f"Retrying update with fallback: {update_err}")
                cur.execute(
                    "UPDATE Products SET name=:n, category_id=:cid, brand_id=:bid, price=:p, cost_price=:cp, stock=:s, description=:d, image_path=:img "
                    "WHERE product_id=:pid",
                    {'n': name, 'cid': category_id, 'bid': brand_id, 'p': price, 'cp': cost_price, 's': stock, 'd': description,
                     'img': image_path, 'pid': product_id},
                )

            cur.execute("SELECT COUNT(*) FROM ProductMedia WHERE product_id = :pid", {'pid': product_id})
            existing_count = cur.fetchone()[0]
            gallery_b64 = request.form.getlist('gallery_base64')
            _save_gallery_media(cur, product_id, request.files.getlist('media'), existing_count, base64_media_list=gallery_b64)

            # Update existing color variants
            existing_ids = request.form.getlist('existing_color_id')
            existing_names = request.form.getlist('existing_color_name')
            existing_codes = request.form.getlist('existing_color_code')
            existing_stocks = request.form.getlist('existing_color_stock')
            existing_b64s = request.form.getlist('existing_color_image_base64')

            for i, cid in enumerate(existing_ids):
                try:
                    cid_int = int(cid)
                    cname = existing_names[i].strip() if i < len(existing_names) else ''
                    if not cname:
                        continue
                    ccode = existing_codes[i].strip() if i < len(existing_codes) and existing_codes[i] else '#000000'
                    try:
                        cstock = int(existing_stocks[i]) if i < len(existing_stocks) and existing_stocks[i] else 0
                    except ValueError:
                        cstock = 0
                    
                    cimg = existing_b64s[i] if i < len(existing_b64s) and existing_b64s[i] and existing_b64s[i].startswith('data:image/') else None
                    if cimg:
                        cur.execute(
                            "UPDATE ProductColors SET color_name = :cn, color_code = :cc, image_path = :img, stock = :stk, sort_order = :so WHERE color_id = :cid AND product_id = :pid",
                            {'cn': cname, 'cc': ccode, 'img': cimg, 'stk': cstock, 'so': i, 'cid': cid_int, 'pid': product_id}
                        )
                    else:
                        cur.execute(
                            "UPDATE ProductColors SET color_name = :cn, color_code = :cc, stock = :stk, sort_order = :so WHERE color_id = :cid AND product_id = :pid",
                            {'cn': cname, 'cc': ccode, 'stk': cstock, 'so': i, 'cid': cid_int, 'pid': product_id}
                        )
                except Exception as e:
                    current_app.logger.warning(f"Error updating existing color #{cid}: {e}")

            # Save newly added color variants
            _save_product_colors(cur, product_id, request.form, request.files)

            log_admin_action(cur, current_user_id(), 'product.update', 'Product', product_id, f'name={name}')
            get_db().commit()
            flash('Product updated successfully.', 'success')
            return redirect(url_for('admin.products'))
        except Exception as e:
            get_db().rollback()
            current_app.logger.exception(f'Error updating product #{product_id}: {e}')
            flash(f'Failed to update product: {str(e)}', 'error')
            return redirect(url_for('admin.edit_product', product_id=product_id))

    try:
        cur.execute(
            "SELECT product_id, category_id, name, price, NVL(cost_price, 0), stock, description, image_path, "
            "       delivery_time_text, free_delivery, technical_specs, highlights, box_contents, brand_id FROM Products WHERE product_id = :pid",
            {'pid': product_id},
        )
        product = cur.fetchone()
    except Exception:
        cur.execute(
            "SELECT product_id, category_id, name, price, NVL(cost_price, 0), stock, description, image_path, "
            "       delivery_time_text, free_delivery, NULL, NULL, NULL, NULL FROM Products WHERE product_id = :pid",
            {'pid': product_id},
        )
        product = cur.fetchone()

    if not product:
        flash('Product not found.', 'error')
        return redirect(url_for('admin.products'))

    cur.execute("SELECT category_id, category_name FROM Categories ORDER BY category_name")
    categories = cur.fetchall()
    try:
        cur.execute("SELECT brand_id, brand_name FROM Brands WHERE is_active = 1 ORDER BY brand_name")
        brands = cur.fetchall()
    except Exception:
        brands = []
    cur.execute(
        "SELECT media_id, media_path, media_type FROM ProductMedia WHERE product_id = :pid ORDER BY sort_order",
        {'pid': product_id},
    )
    gallery = cur.fetchall()

    try:
        cur.execute(
            "SELECT color_id, color_name, color_code, image_path, stock, sort_order FROM ProductColors "
            "WHERE product_id = :pid ORDER BY sort_order, color_id",
            {'pid': product_id},
        )
        colors = cur.fetchall()
    except Exception:
        colors = []

    return render_template(
        'admin/edit_product.html', product=product, categories=categories, brands=brands, gallery=gallery,
        colors=colors, max_media=MAX_PRODUCT_MEDIA,
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


def _handle_image_input(req, file_field_name='image_file', url_field_name='image_url', max_dim=800):
    """Returns (Base64 string or URL, error_message or None)."""
    file = req.files.get(file_field_name)
    if file and file.filename:
        ok, err, data_url, _kind = process_upload(file, allow_video=False, max_dimension=max_dim)
        if not ok:
            return None, err
        return data_url, None
    url = req.form.get(url_field_name, '').strip()
    if url:
        return url, None
    return None, None



# ── CATEGORIES ───────────────────────────────────────────────────
@admin_bp.route('/categories')
@admin_required
def categories():
    cur = get_db().cursor()
    cur.execute(
        "SELECT c.category_id, c.category_name, "
        "       (SELECT COUNT(*) FROM Products p WHERE p.category_id = c.category_id) AS product_count, "
        "       c.icon_name, c.image_path, c.sort_order "
        "FROM Categories c ORDER BY NVL(c.sort_order, 0), c.category_name"
    )
    return render_template('admin/categories.html', categories=cur.fetchall())


@admin_bp.route('/categories/add', methods=['POST'])
@admin_required
def add_category():
    name = request.form.get('category_name', '').strip()
    icon_name = request.form.get('icon_name', '').strip() or 'bi-tag'
    try:
        sort_order = int(request.form.get('sort_order', 0) or 0)
    except ValueError:
        sort_order = 0
    ok, err = validate_required_text(name, 'Category name', min_len=2, max_len=100)
    if not ok:
        flash(err, 'error')
        return redirect(url_for('admin.categories'))

    img_data, img_err = _handle_image_input(request, 'image_file', 'image_url', max_dim=600)
    if img_err:
        flash(img_err, 'error')
        return redirect(url_for('admin.categories'))

    cur = get_db().cursor()
    cur.execute(
        "INSERT INTO Categories (category_id, category_name, icon_name, image_path, sort_order) "
        "VALUES (categories_seq.NEXTVAL, :n, :icon, :img, :so)",
        {'n': name, 'icon': icon_name, 'img': img_data, 'so': sort_order},
    )
    cur.execute("SELECT categories_seq.CURRVAL FROM dual")
    log_admin_action(cur, current_user_id(), 'category.create', 'Category', cur.fetchone()[0], f'name={name}')
    get_db().commit()
    invalidate_categories()
    flash('Category added successfully.', 'success')
    return redirect(url_for('admin.categories'))


@admin_bp.route('/categories/edit/<int:category_id>', methods=['POST'])
@admin_required
def edit_category(category_id):
    name = request.form.get('category_name', '').strip()
    icon_name = request.form.get('icon_name', '').strip() or 'bi-tag'
    try:
        sort_order = int(request.form.get('sort_order', 0) or 0)
    except ValueError:
        sort_order = 0
    remove_image = request.form.get('remove_image') == '1'

    ok, err = validate_required_text(name, 'Category name', min_len=2, max_len=100)
    if not ok:
        flash(err, 'error')
        return redirect(url_for('admin.categories'))

    img_data, img_err = _handle_image_input(request, 'image_file', 'image_url', max_dim=600)
    if img_err:
        flash(img_err, 'error')
        return redirect(url_for('admin.categories'))

    cur = get_db().cursor()
    if remove_image:
        cur.execute(
            "UPDATE Categories SET category_name = :n, icon_name = :icon, image_path = NULL, sort_order = :so "
            "WHERE category_id = :cid",
            {'n': name, 'icon': icon_name, 'so': sort_order, 'cid': category_id},
        )
    elif img_data:
        cur.execute(
            "UPDATE Categories SET category_name = :n, icon_name = :icon, image_path = :img, sort_order = :so "
            "WHERE category_id = :cid",
            {'n': name, 'icon': icon_name, 'img': img_data, 'so': sort_order, 'cid': category_id},
        )
    else:
        cur.execute(
            "UPDATE Categories SET category_name = :n, icon_name = :icon, sort_order = :so "
            "WHERE category_id = :cid",
            {'n': name, 'icon': icon_name, 'so': sort_order, 'cid': category_id},
        )

    log_admin_action(cur, current_user_id(), 'category.edit', 'Category', category_id, f'name={name}')
    get_db().commit()
    invalidate_categories()
    flash('Category updated successfully.', 'success')
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
            invalidate_categories()
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
            invalidate_categories()
            flash(f'Category and {len(product_ids)} product(s) permanently deleted.', 'success')

        else:  # simple delete
            cur.execute("DELETE FROM Categories WHERE category_id = :cid", {'cid': category_id})
            log_admin_action(cur, current_user_id(), 'category.delete', 'Category', category_id)
            get_db().commit()
            invalidate_categories()
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


# ── BRANDS / COMPANIES ────────────────────────────────────────────
@admin_bp.route('/brands')
@admin_required
def brands():
    cur = get_db().cursor()
    cur.execute(
        "SELECT b.brand_id, b.brand_name, b.subtitle, b.logo_path, b.badge_text, "
        "       b.badge_color, b.search_query, b.sort_order, b.is_active, "
        "       (SELECT COUNT(*) FROM Products p WHERE LOWER(p.name) LIKE '%' || LOWER(b.brand_name) || '%' OR LOWER(p.description) LIKE '%' || LOWER(b.brand_name) || '%') AS prod_count "
        "FROM Brands b ORDER BY NVL(b.sort_order, 0), b.brand_name"
    )
    return render_template('admin/brands.html', brands=cur.fetchall())


@admin_bp.route('/brands/add', methods=['POST'])
@admin_required
def add_brand():
    name = request.form.get('brand_name', '').strip()
    subtitle = request.form.get('subtitle', '').strip()
    badge_text = request.form.get('badge_text', '').strip() or (name[:2].upper() if len(name) >= 2 else name.upper())
    badge_color = request.form.get('badge_color', 'brand-bg-dark').strip()
    search_query = request.form.get('search_query', '').strip() or name
    try:
        sort_order = int(request.form.get('sort_order', 0) or 0)
    except ValueError:
        sort_order = 0
    is_active = 1 if request.form.get('is_active') == '1' else 0

    ok, err = validate_required_text(name, 'Brand name', min_len=2, max_len=100)
    if not ok:
        flash(err, 'error')
        return redirect(url_for('admin.brands'))

    logo_data, img_err = _handle_image_input(request, 'logo_file', 'logo_url', max_dim=400)
    if img_err:
        flash(img_err, 'error')
        return redirect(url_for('admin.brands'))

    cur = get_db().cursor()
    cur.execute("""
    INSERT INTO Brands (brand_id, brand_name, subtitle, logo_path, badge_text, badge_color, search_query, sort_order, is_active)
    VALUES (brands_seq.NEXTVAL, :bn, :bs, :lp, :bt, :bc, :sq, :so, :ia)
    """, {
        'bn': name, 'bs': subtitle, 'lp': logo_data, 'bt': badge_text,
        'bc': badge_color, 'sq': search_query, 'so': sort_order, 'ia': is_active
    })
    cur.execute("SELECT brands_seq.CURRVAL FROM dual")
    brand_id = cur.fetchone()[0]
    log_admin_action(cur, current_user_id(), 'brand.create', 'Brand', brand_id, f'name={name}')
    get_db().commit()
    invalidate_brands()
    flash(f'Brand "{name}" added successfully.', 'success')
    return redirect(url_for('admin.brands'))


@admin_bp.route('/brands/edit/<int:brand_id>', methods=['POST'])
@admin_required
def edit_brand(brand_id):
    name = request.form.get('brand_name', '').strip()
    subtitle = request.form.get('subtitle', '').strip()
    badge_text = request.form.get('badge_text', '').strip() or (name[:2].upper() if len(name) >= 2 else name.upper())
    badge_color = request.form.get('badge_color', 'brand-bg-dark').strip()
    search_query = request.form.get('search_query', '').strip() or name
    try:
        sort_order = int(request.form.get('sort_order', 0) or 0)
    except ValueError:
        sort_order = 0
    is_active = 1 if request.form.get('is_active') == '1' else 0
    remove_logo = request.form.get('remove_logo') == '1'

    ok, err = validate_required_text(name, 'Brand name', min_len=2, max_len=100)
    if not ok:
        flash(err, 'error')
        return redirect(url_for('admin.brands'))

    logo_data, img_err = _handle_image_input(request, 'logo_file', 'logo_url', max_dim=400)
    if img_err:
        flash(img_err, 'error')
        return redirect(url_for('admin.brands'))

    cur = get_db().cursor()
    if remove_logo:
        cur.execute("""
        UPDATE Brands SET brand_name = :bn, subtitle = :bs, logo_path = NULL, badge_text = :bt,
                          badge_color = :bc, search_query = :sq, sort_order = :so, is_active = :ia
        WHERE brand_id = :bid
        """, {
            'bn': name, 'bs': subtitle, 'bt': badge_text, 'bc': badge_color,
            'sq': search_query, 'so': sort_order, 'ia': is_active, 'bid': brand_id
        })
    elif logo_data:
        cur.execute("""
        UPDATE Brands SET brand_name = :bn, subtitle = :bs, logo_path = :lp, badge_text = :bt,
                          badge_color = :bc, search_query = :sq, sort_order = :so, is_active = :ia
        WHERE brand_id = :bid
        """, {
            'bn': name, 'bs': subtitle, 'lp': logo_data, 'bt': badge_text, 'bc': badge_color,
            'sq': search_query, 'so': sort_order, 'ia': is_active, 'bid': brand_id
        })
    else:
        cur.execute("""
        UPDATE Brands SET brand_name = :bn, subtitle = :bs, badge_text = :bt,
                          badge_color = :bc, search_query = :sq, sort_order = :so, is_active = :ia
        WHERE brand_id = :bid
        """, {
            'bn': name, 'bs': subtitle, 'bt': badge_text, 'bc': badge_color,
            'sq': search_query, 'so': sort_order, 'ia': is_active, 'bid': brand_id
        })

    log_admin_action(cur, current_user_id(), 'brand.edit', 'Brand', brand_id, f'name={name}')
    get_db().commit()
    invalidate_brands()
    flash(f'Brand "{name}" updated successfully.', 'success')
    return redirect(url_for('admin.brands'))


@admin_bp.route('/brands/toggle/<int:brand_id>', methods=['POST'])
@admin_required
def toggle_brand(brand_id):
    cur = get_db().cursor()
    cur.execute("UPDATE Brands SET is_active = 1 - is_active WHERE brand_id = :bid", {'bid': brand_id})
    log_admin_action(cur, current_user_id(), 'brand.toggle', 'Brand', brand_id)
    get_db().commit()
    invalidate_brands()
    flash('Brand visibility updated.', 'success')
    return redirect(url_for('admin.brands'))


@admin_bp.route('/brands/delete/<int:brand_id>', methods=['POST'])
@admin_required
def delete_brand(brand_id):
    cur = get_db().cursor()
    cur.execute("DELETE FROM Brands WHERE brand_id = :bid", {'bid': brand_id})
    log_admin_action(cur, current_user_id(), 'brand.delete', 'Brand', brand_id)
    get_db().commit()
    invalidate_brands()
    flash('Brand deleted successfully.', 'success')
    return redirect(url_for('admin.brands'))


# ── HERO ADS & BANNERS ────────────────────────────────────────────
@admin_bp.route('/banners')
@admin_required
def banners():
    cur = get_db().cursor()
    cur.execute(
        "SELECT banner_id, badge_tag, title, subtitle, cta_text, cta_link, "
        "       gradient_class, image_path, sort_order, is_active "
        "FROM HeroBanners ORDER BY NVL(sort_order, 0), banner_id"
    )
    return render_template('admin/banners.html', banners=cur.fetchall())


@admin_bp.route('/banners/add', methods=['POST'])
@admin_required
def add_banner():
    badge_tag = request.form.get('badge_tag', '').strip()
    title = request.form.get('title', '').strip()
    subtitle = request.form.get('subtitle', '').strip()
    cta_text = request.form.get('cta_text', 'SHOP NOW').strip() or 'SHOP NOW'
    cta_link = request.form.get('cta_link', '/#productsGrid').strip() or '/#productsGrid'
    gradient_class = request.form.get('gradient_class', 'promo-gradient-autumn').strip()
    try:
        sort_order = int(request.form.get('sort_order', 0) or 0)
    except ValueError:
        sort_order = 0
    is_active = 1 if request.form.get('is_active') == '1' else 0

    ok, err = validate_required_text(title, 'Banner title / headline', min_len=2, max_len=150)
    if not ok:
        flash(err, 'error')
        return redirect(url_for('admin.banners'))

    img_data, img_err = _handle_image_input(request, 'banner_image', 'image_url', max_dim=1200)
    if img_err:
        flash(img_err, 'error')
        return redirect(url_for('admin.banners'))

    cur = get_db().cursor()
    cur.execute("""
    INSERT INTO HeroBanners (banner_id, badge_tag, title, subtitle, cta_text, cta_link, gradient_class, image_path, sort_order, is_active)
    VALUES (banners_seq.NEXTVAL, :btg, :btt, :bsb, :bct, :bcl, :bgc, :bimg, :bso, :bia)
    """, {
        'btg': badge_tag, 'btt': title, 'bsb': subtitle, 'bct': cta_text,
        'bcl': cta_link, 'bgc': gradient_class, 'bimg': img_data, 'bso': sort_order, 'bia': is_active
    })
    cur.execute("SELECT banners_seq.CURRVAL FROM dual")
    banner_id = cur.fetchone()[0]
    log_admin_action(cur, current_user_id(), 'banner.create', 'HeroBanner', banner_id, f'title={title}')
    get_db().commit()
    invalidate_banners()
    flash('Promotional banner ad created successfully.', 'success')
    return redirect(url_for('admin.banners'))


@admin_bp.route('/banners/edit/<int:banner_id>', methods=['POST'])
@admin_required
def edit_banner(banner_id):
    badge_tag = request.form.get('badge_tag', '').strip()
    title = request.form.get('title', '').strip()
    subtitle = request.form.get('subtitle', '').strip()
    cta_text = request.form.get('cta_text', 'SHOP NOW').strip() or 'SHOP NOW'
    cta_link = request.form.get('cta_link', '/#productsGrid').strip() or '/#productsGrid'
    gradient_class = request.form.get('gradient_class', 'promo-gradient-autumn').strip()
    try:
        sort_order = int(request.form.get('sort_order', 0) or 0)
    except ValueError:
        sort_order = 0
    is_active = 1 if request.form.get('is_active') == '1' else 0
    remove_image = request.form.get('remove_image') == '1'

    ok, err = validate_required_text(title, 'Banner title / headline', min_len=2, max_len=150)
    if not ok:
        flash(err, 'error')
        return redirect(url_for('admin.banners'))

    img_data, img_err = _handle_image_input(request, 'banner_image', 'image_url', max_dim=1200)
    if img_err:
        flash(img_err, 'error')
        return redirect(url_for('admin.banners'))

    cur = get_db().cursor()
    if remove_image:
        cur.execute("""
        UPDATE HeroBanners SET badge_tag = :btg, title = :btt, subtitle = :bsb, cta_text = :bct,
                               cta_link = :bcl, gradient_class = :bgc, image_path = NULL,
                               sort_order = :bso, is_active = :bia
        WHERE banner_id = :bid
        """, {
            'btg': badge_tag, 'btt': title, 'bsb': subtitle, 'bct': cta_text,
            'bcl': cta_link, 'bgc': gradient_class, 'bso': sort_order, 'bia': is_active, 'bid': banner_id
        })
    elif img_data:
        cur.execute("""
        UPDATE HeroBanners SET badge_tag = :btg, title = :btt, subtitle = :bsb, cta_text = :bct,
                               cta_link = :bcl, gradient_class = :bgc, image_path = :bimg,
                               sort_order = :bso, is_active = :bia
        WHERE banner_id = :bid
        """, {
            'btg': badge_tag, 'btt': title, 'bsb': subtitle, 'bct': cta_text,
            'bcl': cta_link, 'bgc': gradient_class, 'bimg': img_data, 'bso': sort_order, 'bia': is_active, 'bid': banner_id
        })
    else:
        cur.execute("""
        UPDATE HeroBanners SET badge_tag = :btg, title = :btt, subtitle = :bsb, cta_text = :bct,
                               cta_link = :bcl, gradient_class = :bgc,
                               sort_order = :bso, is_active = :bia
        WHERE banner_id = :bid
        """, {
            'btg': badge_tag, 'btt': title, 'bsb': subtitle, 'bct': cta_text,
            'bcl': cta_link, 'bgc': gradient_class, 'bso': sort_order, 'bia': is_active, 'bid': banner_id
        })

    log_admin_action(cur, current_user_id(), 'banner.edit', 'HeroBanner', banner_id, f'title={title}')
    get_db().commit()
    invalidate_banners()
    flash('Promotional banner ad updated successfully.', 'success')
    return redirect(url_for('admin.banners'))


@admin_bp.route('/banners/toggle/<int:banner_id>', methods=['POST'])
@admin_required
def toggle_banner(banner_id):
    cur = get_db().cursor()
    cur.execute("UPDATE HeroBanners SET is_active = 1 - is_active WHERE banner_id = :bid", {'bid': banner_id})
    log_admin_action(cur, current_user_id(), 'banner.toggle', 'HeroBanner', banner_id)
    get_db().commit()
    invalidate_banners()
    flash('Banner active status updated.', 'success')
    return redirect(url_for('admin.banners'))


@admin_bp.route('/banners/delete/<int:banner_id>', methods=['POST'])
@admin_required
def delete_banner(banner_id):
    cur = get_db().cursor()
    cur.execute("DELETE FROM HeroBanners WHERE banner_id = :bid", {'bid': banner_id})
    log_admin_action(cur, current_user_id(), 'banner.delete', 'HeroBanner', banner_id)
    get_db().commit()
    invalidate_banners()
    flash('Promotional banner deleted successfully.', 'success')
    return redirect(url_for('admin.banners'))


# ── ORDERS ───────────────────────────────────────────────────────
@admin_bp.route('/orders')
@admin_required
def orders():
    cur = get_db().cursor()
    cur.execute(
        "SELECT o.order_id, u.name, o.order_date, o.total_amount, o.status, o.payment_status, "
        "       o.phone_number, o.payment_method, o.delivery_address "
        "FROM Orders o JOIN Users u ON o.user_id = u.user_id ORDER BY o.order_date DESC"
    )
    return render_template('admin/orders.html', orders=cur.fetchall())


@admin_bp.route('/orders/<int:order_id>')
@admin_required
def order_detail(order_id):
    cur = get_db().cursor()
    try:
        try:
            cur.execute(
                """
                SELECT o.order_id, u.name, u.email, o.order_date, o.total_amount, o.status,
                       o.phone_number, o.delivery_address, o.payment_method, o.payment_status,
                       o.payment_proof_path, o.advance_amount, o.coupon_code, o.coupon_discount_amount,
                       o.loyalty_points_redeemed, o.loyalty_discount_amount, o.loyalty_points_earned,
                       o.cashback_points_awarded, o.payment_rejection_reason,
                       o.cash_received_at, o.cash_received_by
                FROM Orders o LEFT JOIN Users u ON o.user_id = u.user_id WHERE o.order_id = :1
                """,
                [order_id],
            )
            order = cur.fetchone()
        except Exception:
            # Fallback if cash_received_at / cash_received_by columns are not yet present
            cur.execute(
                """
                SELECT o.order_id, u.name, u.email, o.order_date, o.total_amount, o.status,
                       o.phone_number, o.delivery_address, o.payment_method, o.payment_status,
                       o.payment_proof_path, o.advance_amount, o.coupon_code, o.coupon_discount_amount,
                       o.loyalty_points_redeemed, o.loyalty_discount_amount, o.loyalty_points_earned,
                       o.cashback_points_awarded, o.payment_rejection_reason,
                       NULL, NULL
                FROM Orders o LEFT JOIN Users u ON o.user_id = u.user_id WHERE o.order_id = :1
                """,
                [order_id],
            )
            order = cur.fetchone()

        if not order:
            flash('Order not found.', 'error')
            return redirect(url_for('admin.orders'))

        # Safe normalization for order values
        order_list = list(order)
        order_list[1] = order_list[1] or 'Customer'
        order_list[2] = order_list[2] or ''
        order_list[4] = float(order_list[4] or 0.0)
        order_list[11] = float(order_list[11] or 0.0)
        order_list[13] = float(order_list[13] or 0.0)
        order_list[14] = int(order_list[14] or 0)
        order_list[15] = float(order_list[15] or 0.0)
        order_list[16] = int(order_list[16] or 0)
        order_list[17] = int(order_list[17] or 0)
        order = tuple(order_list)

        try:
            cur.execute(
                "SELECT p.name, oi.quantity, oi.unit_price, NVL(p.cost_price, 0), oi.selected_color "
                "FROM OrderItems oi JOIN Products p ON oi.product_id = p.product_id WHERE oi.order_id = :1",
                [order_id],
            )
            raw_items = cur.fetchall()
        except Exception:
            cur.execute(
                "SELECT p.name, oi.quantity, oi.unit_price, 0, NULL "
                "FROM OrderItems oi JOIN Products p ON oi.product_id = p.product_id WHERE oi.order_id = :1",
                [order_id],
            )
            raw_items = cur.fetchall()

        items = []
        total_order_cost = 0.0
        items_subtotal = 0.0
        for name, qty, unit_price, cost_price, sel_color in raw_items:
            item_total = qty * float(unit_price or 0.0)
            item_cost = qty * float(cost_price or 0.0)
            item_profit = item_total - item_cost
            items_subtotal += item_total
            total_order_cost += item_cost
            items.append((name, qty, unit_price, cost_price, item_total, item_cost, item_profit, sel_color))

        realized_revenue = float(order[4] or 0.0)
        coupon_discount = float(order[13] or 0.0)
        loyalty_discount = float(order[15] or 0.0)
        total_discounts = coupon_discount + loyalty_discount
        net_order_profit = realized_revenue - total_order_cost
        margin_pct = (net_order_profit / realized_revenue * 100) if realized_revenue > 0 else 0.0

        cash_received_at = order[19]
        pay_method = order[8]
        pay_status = order[9]
        payment_confirmed = (cash_received_at is not None) or \
                            (pay_method == 'bank_transfer' and pay_status == 'verified')

        financials = {
            'items_subtotal': items_subtotal,
            'total_cost': total_order_cost,
            'coupon_discount': coupon_discount,
            'loyalty_discount': loyalty_discount,
            'total_discounts': total_discounts,
            'realized_revenue': realized_revenue,
            'net_profit': net_order_profit,
            'margin_pct': margin_pct,
            'confirmed': payment_confirmed,
            'cash_received_at': cash_received_at,
        }

        try:
            cur.execute("SELECT amount, payment_date, method FROM Payments WHERE order_id = :1", [order_id])
            payment = cur.fetchone()
        except Exception:
            payment = None

        customer_phone = order[6]
        customer_name = order[1]
        order_total = order[4]
        order_status = order[5]
        delivery_addr = order[7]

        whatsapp_link = get_whatsapp_order_link(
            customer_phone, order_id, customer_name, order_total,
            status=order_status, payment_method=pay_method, address=delivery_addr, intent='status'
        )
        wa_links = {
            'default': whatsapp_link,
            'confirm': get_whatsapp_order_link(
                customer_phone, order_id, customer_name, order_total,
                status='pending', payment_method=pay_method, address=delivery_addr, intent='confirm'
            ),
            'shipped': get_whatsapp_order_link(
                customer_phone, order_id, customer_name, order_total,
                status='shipped', payment_method=pay_method, address=delivery_addr, intent='shipped'
            ),
            'delivered': get_whatsapp_order_link(
                customer_phone, order_id, customer_name, order_total,
                status='delivered', payment_method=pay_method, address=delivery_addr, intent='delivered'
            ),
            'verify_request': get_whatsapp_order_link(
                customer_phone, order_id, customer_name, order_total,
                status=order_status, payment_method=pay_method, address=delivery_addr, intent='verify_request'
            ),
            'payment_verified': get_whatsapp_order_link(
                customer_phone, order_id, customer_name, order_total,
                status=order_status, payment_method=pay_method, address=delivery_addr, intent='payment_verified'
            ),
        }

        return render_template(
            'admin/order_detail.html', order=order, items=items, payment=payment,
            financials=financials, whatsapp_link=whatsapp_link, wa_links=wa_links,
        )
    except Exception as e:
        current_app.logger.error(f"Error viewing order #{order_id}: {e}")
        flash(f"Failed to load order #{order_id}: {e}", 'error')
        return redirect(url_for('admin.orders'))



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
    status_filter = request.args.get('status', 'pending_verification').strip().lower()

    # Query counts for tabs
    cur.execute("SELECT COUNT(*) FROM Orders WHERE payment_method = 'bank_transfer' AND payment_status = 'pending_verification'")
    pending_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM Orders WHERE payment_method = 'bank_transfer' AND payment_status = 'verified'")
    verified_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM Orders WHERE payment_method = 'bank_transfer' AND payment_status = 'rejected'")
    rejected_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM Orders WHERE payment_method = 'bank_transfer'")
    all_count = cur.fetchone()[0]

    # Query sum of pending amount
    cur.execute("SELECT NVL(SUM(total_amount), 0) FROM Orders WHERE payment_method = 'bank_transfer' AND payment_status = 'pending_verification'")
    pending_total_amount = float(cur.fetchone()[0])

    base_query = """
        SELECT o.order_id, u.name, u.email, o.phone_number, o.total_amount, o.payment_method,
               o.advance_amount, o.payment_proof_path, o.order_date, o.payment_status,
               o.payment_verified_at, o.payment_rejection_reason, o.delivery_address, o.status
        FROM Orders o JOIN Users u ON o.user_id = u.user_id
        WHERE o.payment_method = 'bank_transfer'
    """

    if status_filter == 'pending_verification':
        base_query += " AND o.payment_status = 'pending_verification'"
    elif status_filter == 'verified':
        base_query += " AND o.payment_status = 'verified'"
    elif status_filter == 'rejected':
        base_query += " AND o.payment_status = 'rejected'"
    elif status_filter == 'all':
        pass
    else:
        status_filter = 'pending_verification'
        base_query += " AND o.payment_status = 'pending_verification'"

    base_query += " ORDER BY o.order_date DESC"
    cur.execute(base_query)
    rows = cur.fetchall()

    return render_template(
        'admin/payment_verification.html',
        pending=rows,
        status_filter=status_filter,
        pending_count=pending_count,
        verified_count=verified_count,
        rejected_count=rejected_count,
        all_count=all_count,
        pending_total_amount=pending_total_amount,
    )


@admin_bp.route('/payments/<int:order_id>/verify', methods=['POST'])
@admin_required
def verify_payment(order_id):
    cur = get_db().cursor()
    cur.execute(
        "SELECT u.user_id, u.name, u.email, o.total_amount, o.payment_method, o.phone_number, o.delivery_address "
        "FROM Orders o JOIN Users u ON o.user_id = u.user_id WHERE o.order_id = :1",
        [order_id],
    )
    row = cur.fetchone()
    if not row:
        flash('Order not found.', 'error')
        return redirect(url_for('admin.payment_verification'))
    _user_id, name, email, total_amount, method, phone, address = row

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
    whatsapp_link = get_whatsapp_order_link(
        phone, order_id, name, total_amount,
        status='pending', payment_method=method, address=address, intent='payment_verified'
    )
    flash(f'Payment for Order #{order_id} verified successfully! Confirmation email sent.', 'success')

    next_url = request.form.get('next') or url_for('admin.order_detail', order_id=order_id)
    separator = '&' if '?' in next_url else '?'
    return redirect(f"{next_url}{separator}whatsapp={quote(whatsapp_link)}")


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
    flash(f'Payment for Order #{order_id} rejected.', 'success')
    next_url = request.form.get('next') or url_for('admin.order_detail', order_id=order_id)
    return redirect(next_url)


@admin_bp.route('/orders/<int:order_id>/mark_payment_received', methods=['GET', 'POST'])
@admin_required
def mark_payment_received(order_id):
    """Mark that physical cash has been collected (primarily for COD orders).
    For bank transfers, payment is confirmed via verify_payment; this route still
    allows re-confirming if needed."""
    if request.method == 'GET':
        return redirect(url_for('admin.order_detail', order_id=order_id))

    cur = get_db().cursor()
    try:
        cur.execute(
            "SELECT o.payment_method, o.payment_status, o.cash_received_at, o.status, o.total_amount, u.name "
            "FROM Orders o LEFT JOIN Users u ON o.user_id = u.user_id WHERE o.order_id = :1",
            [order_id],
        )
        row = cur.fetchone()
        if not row:
            flash('Order not found.', 'error')
            return redirect(url_for('admin.orders'))

        pay_method, pay_status, cash_at, order_status, total_amount, customer_name = row
        total_amount = float(total_amount or 0.0)
        customer_name = customer_name or 'Customer'

        if cash_at is not None:
            flash('Cash already marked as received for this order.', 'info')
            return redirect(url_for('admin.order_detail', order_id=order_id))

        # For bank transfers that haven't been payment-verified yet, block
        if pay_method == 'bank_transfer' and pay_status != 'verified':
            flash('Bank transfer payment must be verified first before marking as received.', 'warning')
            return redirect(url_for('admin.order_detail', order_id=order_id))

        uid = current_user_id()
        try:
            cur.execute(
                "UPDATE Orders SET cash_received_at = SYSDATE, cash_received_by = :uid WHERE order_id = :oid",
                {'uid': uid, 'oid': order_id},
            )
        except Exception:
            cur.execute(
                "UPDATE Orders SET cash_received_at = SYSDATE WHERE order_id = :oid",
                {'oid': order_id},
            )

        log_admin_action(cur, uid, 'payment.cash_received', 'Order', order_id,
                         f'method={pay_method}, amount={total_amount}')
        get_db().commit()

        if pay_method == 'cod':
            flash(f'✓ Cash payment of Rs {total_amount:,.2f} marked as received from {customer_name}. '
                  f'Profit for this order is now confirmed.', 'success')
        else:
            flash(f'✓ Payment of Rs {total_amount:,.2f} confirmed received for {customer_name}. '
                  f'This order is now counted in confirmed net profit.', 'success')
    except Exception as e:
        get_db().rollback()
        current_app.logger.error(f"Error marking payment received for order #{order_id}: {e}")
        flash(f'Failed to update payment status: {e}', 'error')

    return redirect(url_for('admin.order_detail', order_id=order_id))



@admin_bp.route('/coupons')
@admin_required
def coupons():
    cur = get_db().cursor()
    cur.execute(
        "SELECT coupon_id, code, NVL(discount_type, 'percentage'), discount_percent, discount_amount, "
        "max_uses, used_count, valid_from, valid_to, active "
        "FROM Coupons ORDER BY created_at DESC"
    )
    coupons_list = cur.fetchall()
    settings = sitesettings.get_settings(cur)
    margin_floor = sitesettings.get_setting_number(settings, 'min_profit_margin_floor', 300)
    return render_template('admin/coupons.html', coupons=coupons_list, margin_floor=margin_floor)


@admin_bp.route('/coupons/add', methods=['POST'])
@admin_required
def add_coupon():
    code = request.form.get('code', '').strip().upper()
    discount_type = request.form.get('discount_type', 'percentage').strip().lower()
    
    if discount_type == 'fixed':
        discount_value = request.form.get('discount_amount') or request.form.get('discount_value')
    else:
        discount_type = 'percentage'
        discount_value = request.form.get('discount_percent') or request.form.get('discount_value')

    ok, err = validate_required_text(code, 'Coupon code', min_len=3, max_len=30)
    val = None
    if ok:
        ok, err, val = validate_coupon_discount(discount_type, discount_value)
    if not ok:
        flash(err, 'error')
        return redirect(url_for('admin.coupons'))

    pct = val if discount_type == 'percentage' else None
    amt = val if discount_type == 'fixed' else 0.0

    max_uses = request.form.get('max_uses') or None
    valid_to = request.form.get('valid_to') or None

    cur = get_db().cursor()
    try:
        cur.execute(
            "INSERT INTO Coupons (coupon_id, code, discount_type, discount_percent, discount_amount, max_uses, valid_to, created_by) "
            "VALUES (coupons_seq.NEXTVAL, :c, :dt, :p, :a, :m, TO_DATE(:vt, 'YYYY-MM-DD'), :u)",
            {'c': code, 'dt': discount_type, 'p': pct, 'a': amt, 'm': max_uses, 'vt': valid_to, 'u': current_user_id()},
        )
        log_admin_action(cur, current_user_id(), 'coupon.create', 'Coupon', None, f'code={code}, type={discount_type}, val={val}')
        get_db().commit()
        flash('Coupon created successfully.', 'success')
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
        invalidate_site_settings()
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
