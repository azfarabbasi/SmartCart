import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_db
from extensions import limiter
from security import is_locked_out, record_login_attempt
from validators import validate_email_format, validate_required_text

auth_bp = Blueprint('auth', __name__)


def _safe_next(next_url):
    if next_url and next_url.startswith('/') and not next_url.startswith('//'):
        return next_url
    return None


def send_registration_email(to_email, name):
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Welcome to SmartCart!'
        msg['From'] = current_app.config['EMAIL_USER']
        msg['To'] = to_email
        body = f"""
        <html><body>
        <h2>Welcome, {name}!</h2>
        <p>Your account has been successfully registered on <strong>SmartCart</strong>.</p>
        <p>You can now log in and start shopping.</p>
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
        current_app.logger.warning(f'Registration email failed: {e}')


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('10 per minute')
def login():
    next_url = _safe_next(request.args.get('next') or request.form.get('next'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        cur = get_db().cursor()

        if is_locked_out(cur, email):
            flash(f'Too many failed attempts for this account. Try again in a few minutes.', 'error')
            return render_template('login.html', next=next_url)

        cur.execute(
            "SELECT user_id, name, password, role FROM Users WHERE LOWER(email) = :e",
            {'e': email.lower()},
        )
        user = cur.fetchone()

        ok = False
        if user:
            stored_pw = user[2] or ''
            try:
                ok = check_password_hash(stored_pw, password)
            except Exception:
                ok = False
            # Backward compatibility for any remaining plain-text passwords, auto-upgraded on success.
            if not ok and stored_pw == password:
                ok = True
                cur.execute(
                    "UPDATE Users SET password = :p WHERE user_id = :p_uid",
                    {'p': generate_password_hash(password), 'p_uid': user[0]},
                )

        record_login_attempt(cur, email, ok)
        get_db().commit()

        if ok:
            session.clear()
            session['user_id'] = user[0]
            session['name'] = user[1]
            session['role'] = user[3]
            session.permanent = True

            if next_url:
                return redirect(next_url)
            if user[3] == 'admin':
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('customer.index'))

        flash('Invalid email or password.', 'error')

    return render_template('login.html', next=next_url)


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit('10 per minute')
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        ok, err = validate_required_text(name, 'Name', min_len=2, max_len=100)
        if ok:
            ok, err = validate_email_format(email)
        if ok:
            ok, err = validate_required_text(password, 'Password', min_len=6, max_len=255)
        if not ok:
            flash(err, 'error')
            return render_template('register.html')

        cur = get_db().cursor()
        cur.execute("SELECT COUNT(*) FROM Users WHERE LOWER(email) = :e", {'e': email})
        if cur.fetchone()[0] > 0:
            flash('Email already registered. Please use a different email.', 'error')
            return render_template('register.html')

        hashed = generate_password_hash(password)
        cur.execute(
            "INSERT INTO Users (user_id, name, email, password, role, created_at) "
            "VALUES (users_seq.NEXTVAL, :n, :e, :p, 'customer', SYSDATE)",
            {'n': name, 'e': email, 'p': hashed},
        )
        get_db().commit()

        send_registration_email(email, name)
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
