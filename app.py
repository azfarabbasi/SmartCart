from flask import Flask, render_template, request, redirect, url_for, session, flash
import oracledb
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = 'smartcart_secret_2025'
oracledb.init_oracle_client(lib_dir=r"C:\oraclexe\app\oracle\product\11.2.0\server\bin")


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
DB_USER     = 'smart_cart'
DB_PASSWORD = 'smartcart123'
DB_DSN      = 'localhost:1521/XE'

UPLOAD_FOLDER      = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

EMAIL_HOST     = 'smtp.gmail.com'
EMAIL_PORT     = 587
EMAIL_USER     = 'nahihaiemail53@gmail.com'
EMAIL_PASSWORD = 'ixnc ibdq olmj xmjt'   # Gmail App Password

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────
def get_db():
    conn = oracledb.connect(user=DB_USER, password=DB_PASSWORD, dsn=DB_DSN)
    return conn


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def send_registration_email(to_email, name):
    try:
        msg            = MIMEMultipart('alternative')
        msg['Subject'] = 'Welcome to SmartCart!'
        msg['From']    = EMAIL_USER
        msg['To']      = to_email
        body = f"""
        <html><body>
        <h2>Welcome, {name}!</h2>
        <p>Your account has been successfully registered on <strong>SmartCart</strong>.</p>
        <p>You can now log in and start shopping.</p>
        <br><p>— The SmartCart Team</p>
        </body></html>
        """
        msg.attach(MIMEText(body, 'html'))
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_USER, to_email, msg.as_string())
        server.quit()
    except Exception as e:
        print(f"Email error: {e}")


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────────
@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email'].strip()
        password = request.form['password'].strip()

        conn = get_db()
        cur  = conn.cursor()
        cur.execute(
            "SELECT user_id, name, password, role FROM Users WHERE LOWER(email) = :e",
            {'e': email.lower()}
        )
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            stored_pw = user[2] or ""
            ok = False

            try:
                ok = check_password_hash(stored_pw, password)
            except Exception:
                ok = False

            # Backward compatibility for any remaining plain-text passwords
            if not ok and stored_pw == password:
                ok = True
                try:
                    conn2 = get_db()
                    cur2  = conn2.cursor()
                    cur2.execute(
                        "UPDATE Users SET password = :p WHERE user_id = :uid",
                        {"p": generate_password_hash(password), "uid": user[0]}
                    )
                    conn2.commit()
                    cur2.close()
                    conn2.close()
                except Exception:
                    pass

            if ok:
                session['user_id'] = user[0]
                session['name']    = user[1]
                session['role']    = user[3]   # reads 'admin' or 'customer' from DB

                if user[3] == 'admin':
                    return redirect(url_for('admin_dashboard'))
                return redirect(url_for('customer_home'))

        flash('Invalid email or password.', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name     = request.form['name'].strip()
        email    = request.form['email'].strip().lower()
        password = request.form['password'].strip()

        conn = get_db()
        cur  = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM Users WHERE LOWER(email) = :e", {'e': email})
        if cur.fetchone()[0] > 0:
            flash('Email already registered. Please use a different email.', 'error')
            cur.close()
            conn.close()
            return render_template('register.html')

        hashed = generate_password_hash(password)
        cur.execute(
            "INSERT INTO Users (user_id, name, email, password, role, created_at) "
            "VALUES (users_seq.NEXTVAL, :n, :e, :p, 'customer', SYSDATE)",
            {'n': name, 'e': email, 'p': hashed}
        )
        conn.commit()
        cur.close()
        conn.close()

        send_registration_email(email, name)
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ─────────────────────────────────────────────
# CUSTOMER ROUTES
# ─────────────────────────────────────────────
@app.route('/home')
@login_required
def customer_home():
    category_id = request.args.get('category_id')
    search      = request.args.get('search', '').strip()

    conn = get_db()
    cur  = conn.cursor()

    query  = ("SELECT p.product_id, p.name, p.price, p.stock, p.description, "
              "p.image_path, c.category_name "
              "FROM Products p JOIN Categories c ON p.category_id = c.category_id "
              "WHERE 1=1")
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

    cur.close()
    conn.close()
    return render_template('customer/home.html', products=products,
                           categories=categories,
                           selected_category=category_id, search=search)


@app.route('/product/<int:product_id>')
@login_required
def product_detail(product_id):
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "SELECT p.product_id, p.name, p.price, p.stock, p.description, "
        "p.image_path, c.category_name "
        "FROM Products p JOIN Categories c ON p.category_id = c.category_id "
        "WHERE p.product_id = :pid",
        {'pid': product_id}
    )
    product = cur.fetchone()
    cur.close()
    conn.close()
    if not product:
        flash('Product not found.', 'error')
        return redirect(url_for('customer_home'))
    return render_template('customer/product_detail.html', product=product)


# ── CART ──────────────────────────────────────
@app.route('/cart')
@login_required
def view_cart():
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "SELECT c.cart_id, p.product_id, p.name, p.price, c.quantity, p.image_path "
        "FROM Cart c JOIN Products p ON c.product_id = p.product_id "
        "WHERE c.user_id = :1",
        [session['user_id']]
    )
    items = cur.fetchall()
    cur.close()
    conn.close()
    total = sum(row[3] * row[4] for row in items)
    return render_template('customer/cart.html', items=items, total=total)


@app.route('/cart/add', methods=['POST'])
@login_required
def add_to_cart():
    product_id = int(request.form['product_id'])
    quantity   = int(request.form.get('quantity', 1))

    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "SELECT cart_id FROM Cart WHERE user_id = :1 AND product_id = :2",
        [session['user_id'], product_id]
    )
    existing = cur.fetchone()

    if existing:
        cur.execute(
            "UPDATE Cart SET quantity = quantity + :1 WHERE cart_id = :2",
            [quantity, existing[0]]
        )
    else:
        cur.execute(
            "INSERT INTO Cart (cart_id, user_id, product_id, quantity) "
            "VALUES (cart_seq.NEXTVAL, :1, :2, :3)",
            [session['user_id'], product_id, quantity]
        )
    conn.commit()
    cur.close()
    conn.close()
    flash('Item added to cart.', 'success')
    return redirect(url_for('view_cart'))


@app.route('/cart/update', methods=['POST'])
@login_required
def update_cart():
    cart_id  = int(request.form['cart_id'])
    quantity = int(request.form['quantity'])

    conn = get_db()
    cur  = conn.cursor()
    if quantity <= 0:
        cur.execute(
            "DELETE FROM Cart WHERE cart_id = :1 AND user_id = :2",
            [cart_id, session['user_id']]
        )
    else:
        cur.execute(
            "UPDATE Cart SET quantity = :1 WHERE cart_id = :2 AND user_id = :3",
            [quantity, cart_id, session['user_id']]
        )
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('view_cart'))


@app.route('/cart/remove/<int:cart_id>')
@login_required
def remove_from_cart(cart_id):
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "DELETE FROM Cart WHERE cart_id = :1 AND user_id = :2",
        [cart_id, session['user_id']]
    )
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('view_cart'))


# ── WISHLIST ──────────────────────────────────
@app.route('/wishlist')
@login_required
def view_wishlist():
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "SELECT w.wishlist_id, p.product_id, p.name, p.price, p.image_path "
        "FROM Wishlist w JOIN Products p ON w.product_id = p.product_id "
        "WHERE w.user_id = :1",
        [session['user_id']]
    )
    items = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('customer/wishlist.html', items=items)


@app.route('/wishlist/add', methods=['POST'])
@login_required
def add_to_wishlist():
    product_id = int(request.form['product_id'])
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM Wishlist WHERE user_id = :1 AND product_id = :2",
        [session['user_id'], product_id]
    )
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO Wishlist (wishlist_id, user_id, product_id) "
            "VALUES (wishlist_seq.NEXTVAL, :1, :2)",
            [session['user_id'], product_id]
        )
        conn.commit()
        flash('Added to wishlist.', 'success')
    else:
        flash('Already in wishlist.', 'info')
    cur.close()
    conn.close()
    return redirect(url_for('view_wishlist'))


@app.route('/wishlist/remove/<int:wishlist_id>')
@login_required
def remove_from_wishlist(wishlist_id):
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "DELETE FROM Wishlist WHERE wishlist_id = :1 AND user_id = :2",
        [wishlist_id, session['user_id']]
    )
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('view_wishlist'))


# ── CHECKOUT / ORDERS ─────────────────────────
@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    conn = get_db()
    cur  = conn.cursor()

    if request.method == 'POST':
        payment_method = request.form.get('payment_method', 'cash')
        phone          = request.form.get('phone', '').strip()
        address        = request.form.get('address', '').strip()

        # Check cart is not empty before calling procedure
        cur.execute("SELECT COUNT(*) FROM Cart WHERE user_id = :1", [session['user_id']])
        if cur.fetchone()[0] == 0:
            flash('Your cart is empty.', 'error')
            cur.close()
            conn.close()
            return redirect(url_for('view_cart'))

        try:
            # Call the stored procedure — triggers fire inside Oracle automatically
            cur.callproc('place_order', [session['user_id'], payment_method, address, phone])
            conn.commit()
            flash('Order placed successfully!', 'success')
            cur.close()
            conn.close()
            return redirect(url_for('order_history'))

        except oracledb.DatabaseError as e:
            error_msg = str(e)
            # ORA-20001 is raised by check_stock_trigger (insufficient stock)
            # ORA-20002 is raised by the procedure itself (empty cart)
            if 'ORA-20001' in error_msg or 'ORA-20002' in error_msg:
                # Extract the readable part after the ORA code
                readable = error_msg.split('ORA-20001:')[-1].split('ORA-20002:')[-1].strip()
                flash(readable, 'error')
            else:
                flash('Order could not be placed. Please try again.', 'error')
            cur.close()
            conn.close()
            return redirect(url_for('view_cart'))

    # GET — show cart summary for confirmation
    cur.execute(
        "SELECT p.name, c.quantity, p.price "
        "FROM Cart c JOIN Products p ON c.product_id = p.product_id "
        "WHERE c.user_id = :1",
        [session['user_id']]
    )
    cart_items = cur.fetchall()
    total = sum(row[1] * row[2] for row in cart_items)
    cur.close()
    conn.close()
    return render_template('customer/checkout.html', cart_items=cart_items, total=total)


@app.route('/orders')
@login_required
def order_history():
    conn = get_db()
    cur  = conn.cursor()
    # Avoid bind parsing edge-cases by using positional binds here.
    cur.execute(
        "SELECT order_id, order_date, total_amount, status "
        "FROM Orders WHERE user_id = :1 ORDER BY order_date DESC",
        [session['user_id']]
    )
    orders = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('customer/orders.html', orders=orders)


@app.route('/orders/<int:order_id>')
@login_required
def order_detail(order_id):
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "SELECT order_id, order_date, total_amount, status, phone_number, delivery_address "
        "FROM Orders WHERE order_id = :1 AND user_id = :2",
        [order_id, session['user_id']]
    )
    order = cur.fetchone()
    if not order:
        flash('Order not found.', 'error')
        cur.close()
        conn.close()
        return redirect(url_for('order_history'))

    cur.execute(
        "SELECT p.name, oi.quantity, oi.unit_price "
        "FROM OrderItems oi JOIN Products p ON oi.product_id = p.product_id "
        "WHERE oi.order_id = :1",
        [order_id]
    )
    items = cur.fetchall()

    cur.execute(
        "SELECT amount, payment_date, method FROM Payments WHERE order_id = :1",
        [order_id]
    )
    payment = cur.fetchone()
    cur.close()
    conn.close()
    return render_template('customer/order_detail.html', order=order, items=items, payment=payment)


# ─────────────────────────────────────────────
# ADMIN ROUTES
# ─────────────────────────────────────────────
@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM Products")
    total_products = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM Orders")
    total_orders = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM Users")          # all DB users are customers
    total_customers = cur.fetchone()[0]
    cur.execute("SELECT NVL(SUM(total_amount), 0) FROM Orders WHERE status != 'cancelled'")
    total_revenue = cur.fetchone()[0]
    cur.execute(
        "SELECT order_id, name, order_date, total_amount, status FROM ("
        "  SELECT o.order_id, u.name, o.order_date, o.total_amount, o.status "
        "  FROM Orders o JOIN Users u ON o.user_id = u.user_id "
        "  ORDER BY o.order_date DESC"
        ") WHERE ROWNUM <= 5"
    )
    recent_orders = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin/dashboard.html',
                           total_products=total_products,
                           total_orders=total_orders,
                           total_customers=total_customers,
                           total_revenue=total_revenue,
                           recent_orders=recent_orders)


# ── PRODUCTS ──────────────────────────────────
@app.route('/admin/products')
@admin_required
def admin_products():
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "SELECT p.product_id, p.name, c.category_name, p.price, p.stock, p.image_path "
        "FROM Products p JOIN Categories c ON p.category_id = c.category_id "
        "ORDER BY p.product_id"
    )
    products = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin/products.html', products=products)


@app.route('/admin/products/add', methods=['GET', 'POST'])
@admin_required
def admin_add_product():
    conn = get_db()
    cur  = conn.cursor()

    if request.method == 'POST':
        name        = request.form['name'].strip()
        category_id = int(request.form['category_id'])
        price       = float(request.form['price'])
        stock       = int(request.form['stock'])
        description = request.form.get('description', '').strip()
        image_path  = None

        file = request.files.get('image')
        if file and file.filename and allowed_file(file.filename):
            filename  = secure_filename(file.filename)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(save_path)
            image_path = f"uploads/{filename}"

        cur.execute(
            "INSERT INTO Products (product_id, category_id, name, price, stock, description, image_path) "
            "VALUES (products_seq.NEXTVAL, :cid, :n, :p, :s, :d, :img)",
            {'cid': category_id, 'n': name, 'p': price, 's': stock, 'd': description, 'img': image_path}
        )
        conn.commit()
        cur.close()
        conn.close()
        flash('Product added successfully.', 'success')
        return redirect(url_for('admin_products'))

    cur.execute("SELECT category_id, category_name FROM Categories ORDER BY category_name")
    categories = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin/add_product.html', categories=categories)


@app.route('/admin/products/edit/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_product(product_id):
    conn = get_db()
    cur  = conn.cursor()

    if request.method == 'POST':
        name        = request.form['name'].strip()
        category_id = int(request.form['category_id'])
        price       = float(request.form['price'])
        stock       = int(request.form['stock'])
        description = request.form.get('description', '').strip()

        # Keep existing image unless a new one is uploaded
        cur.execute("SELECT image_path FROM Products WHERE product_id = :pid", {'pid': product_id})
        row = cur.fetchone()
        image_path = row[0] if row else None

        file = request.files.get('image')
        if file and file.filename and allowed_file(file.filename):
            filename  = secure_filename(file.filename)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(save_path)
            image_path = f"uploads/{filename}"

        cur.execute(
            "UPDATE Products "
            "SET name=:n, category_id=:cid, price=:p, stock=:s, description=:d, image_path=:img "
            "WHERE product_id=:pid",
            {'n': name, 'cid': category_id, 'p': price, 's': stock,
             'd': description, 'img': image_path, 'pid': product_id}
        )
        conn.commit()
        cur.close()
        conn.close()
        flash('Product updated.', 'success')
        return redirect(url_for('admin_products'))

    cur.execute("SELECT * FROM Products WHERE product_id = :pid", {'pid': product_id})
    product = cur.fetchone()
    if not product:
        flash('Product not found.', 'error')
        cur.close()
        conn.close()
        return redirect(url_for('admin_products'))

    cur.execute("SELECT category_id, category_name FROM Categories ORDER BY category_name")
    categories = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin/edit_product.html', product=product, categories=categories)


@app.route('/admin/products/delete/<int:product_id>')
@admin_required
def admin_delete_product(product_id):
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("DELETE FROM Products WHERE product_id = :pid", {'pid': product_id})
        conn.commit()
        flash('Product deleted.', 'success')
    except oracledb.IntegrityError:
        flash('Cannot delete product – it is referenced in existing orders.', 'error')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('admin_products'))


# ── CATEGORIES ────────────────────────────────
@app.route('/admin/categories')
@admin_required
def admin_categories():
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("SELECT category_id, category_name FROM Categories ORDER BY category_name")
    categories = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin/categories.html', categories=categories)


@app.route('/admin/categories/add', methods=['POST'])
@admin_required
def admin_add_category():
    name = request.form['category_name'].strip()
    if not name:
        flash('Category name cannot be empty.', 'error')
        return redirect(url_for('admin_categories'))
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "INSERT INTO Categories (category_id, category_name) VALUES (categories_seq.NEXTVAL, :n)",
        {'n': name}
    )
    conn.commit()
    cur.close()
    conn.close()
    flash('Category added.', 'success')
    return redirect(url_for('admin_categories'))


@app.route('/admin/categories/delete/<int:category_id>')
@admin_required
def admin_delete_category(category_id):
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("DELETE FROM Categories WHERE category_id = :cid", {'cid': category_id})
        conn.commit()
        flash('Category deleted.', 'success')
    except oracledb.IntegrityError:
        flash('Cannot delete category – products are assigned to it.', 'error')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('admin_categories'))


# ── ORDERS ────────────────────────────────────
@app.route('/admin/orders')
@admin_required
def admin_orders():
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "SELECT o.order_id, u.name, o.order_date, o.total_amount, o.status "
        "FROM Orders o JOIN Users u ON o.user_id = u.user_id "
        "ORDER BY o.order_date DESC"
    )
    orders = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin/orders.html', orders=orders)


@app.route('/admin/orders/<int:order_id>')
@admin_required
def admin_order_detail(order_id):
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "SELECT o.order_id, u.name, u.email, o.order_date, o.total_amount, o.status, "
        "       o.phone_number, o.delivery_address "
        "FROM Orders o JOIN Users u ON o.user_id = u.user_id WHERE o.order_id = :1",
        [order_id]
    )
    order = cur.fetchone()
    if not order:
        flash('Order not found.', 'error')
        cur.close()
        conn.close()
        return redirect(url_for('admin_orders'))

    cur.execute(
        "SELECT p.name, oi.quantity, oi.unit_price "
        "FROM OrderItems oi JOIN Products p ON oi.product_id = p.product_id "
        "WHERE oi.order_id = :1",
        [order_id]
    )
    items = cur.fetchall()

    cur.execute(
        "SELECT amount, payment_date, method FROM Payments WHERE order_id = :1",
        [order_id]
    )
    payment = cur.fetchone()
    cur.close()
    conn.close()
    return render_template('admin/order_detail.html', order=order, items=items, payment=payment)


@app.route('/admin/orders/update_status', methods=['POST'])
@admin_required
def admin_update_order_status():
    order_id = int(request.form['order_id'])
    status   = request.form['status']
    allowed  = {'pending', 'shipped', 'delivered', 'cancelled'}
    if status not in allowed:
        flash('Invalid status value.', 'error')
        return redirect(url_for('admin_orders'))

    conn = get_db()
    cur  = conn.cursor()

    # Fetch current status before updating
    cur.execute("SELECT status FROM Orders WHERE order_id = :oid", {'oid': order_id})
    row = cur.fetchone()
    current_status = row[0] if row else None

    cur.execute(
        "UPDATE Orders SET status = :s WHERE order_id = :oid",
        {'s': status, 'oid': order_id}
    )

    # If order is being cancelled, restore stock for all its items
    if status == 'cancelled' and current_status != 'cancelled':
        cur.execute(
            "UPDATE Products p SET p.stock = p.stock + ("
            "    SELECT oi.quantity FROM OrderItems oi"
            "    WHERE oi.product_id = p.product_id AND oi.order_id = :oid"
            ") WHERE p.product_id IN ("
            "    SELECT product_id FROM OrderItems WHERE order_id = :oid"
            ")",
            {'oid': order_id}
        )
        flash('Order cancelled and stock restored.', 'success')
    else:
        flash('Order status updated.', 'success')

    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('admin_order_detail', order_id=order_id))


# ── USERS ─────────────────────────────────────
@app.route('/admin/users')
@admin_required
def admin_users():
    conn = get_db()
    cur  = conn.cursor()
    # Only DB users (all are customers)
    cur.execute(
        "SELECT user_id, name, email, role, created_at FROM Users ORDER BY created_at DESC"
    )
    users = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin/users.html', users=users)


# ── INVENTORY VIEW ────────────────────────────
@app.route('/admin/inventory')
@admin_required
def admin_inventory():
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM AdminInventoryView ORDER BY product_id")
    inventory = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin/inventory.html', inventory=inventory)


if __name__ == '__main__':
    app.run(debug=True)
