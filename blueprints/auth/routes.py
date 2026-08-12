import random
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_db
from extensions import limiter
from security import is_locked_out, record_login_attempt
from validators import validate_email_format, validate_required_text

auth_bp = Blueprint('auth', __name__)

CODE_VALID_MINUTES = 15


def _safe_next(next_url):
    if next_url and next_url.startswith('/') and not next_url.startswith('//'):
        return next_url
    return None


def _send_email(to_email, subject, body_html):
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = current_app.config['EMAIL_USER']
        msg['To'] = to_email
        msg.attach(MIMEText(body_html, 'html'))
        server = smtplib.SMTP(current_app.config['EMAIL_HOST'], current_app.config['EMAIL_PORT'])
        server.starttls()
        server.login(current_app.config['EMAIL_USER'], current_app.config['EMAIL_PASSWORD'])
        server.sendmail(current_app.config['EMAIL_USER'], to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        current_app.logger.warning(f'Email send failed ({subject}): {e}')
        return False


def send_welcome_email(to_email, name):
    _send_email(to_email, 'Welcome to SmartCart!', f"""
        <html><body>
        <h2>Welcome, {name}!</h2>
        <p>Your email is verified and your <strong>SmartCart</strong> account is ready to go.</p>
        <p>You can now log in and start shopping.</p>
        <br><p>&mdash; The SmartCart Team</p>
        </body></html>
    """)


def send_verification_email(to_email, name, code):
    return _send_email(to_email, 'Verify your SmartCart account', f"""
        <html><body>
        <h2>Hi {name},</h2>
        <p>Your SmartCart verification code is:</p>
        <p style="font-size:32px; font-weight:bold; letter-spacing:6px;">{code}</p>
        <p>This code expires in {CODE_VALID_MINUTES} minutes. If you didn't request this, you can ignore this email.</p>
        <br><p>&mdash; The SmartCart Team</p>
        </body></html>
    """)


def _issue_verification_code(cur, user_id, email, name):
    code = f'{random.randint(0, 999999):06d}'
    expires = datetime.now() + timedelta(minutes=CODE_VALID_MINUTES)
    cur.execute(
        "UPDATE Users SET verification_code = :v_code, verification_code_expires = :v_expires "
        "WHERE user_id = :v_user_id",
        {'v_code': code, 'v_expires': expires, 'v_user_id': user_id},
    )
    get_db().commit()
    send_verification_email(email, name, code)


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
            "SELECT user_id, name, password, role, email_verified FROM Users WHERE LOWER(email) = :e",
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

        if ok and not user[4]:
            _issue_verification_code(cur, user[0], email, user[1])
            session['pending_verification_user_id'] = user[0]
            flash('Please verify your email to continue. We just sent you a new code.', 'error')
            return redirect(url_for('auth.verify_email'))

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
        confirm_password = request.form.get('confirm_password', '').strip()

        ok, err = validate_required_text(name, 'Name', min_len=2, max_len=100)
        if ok:
            ok, err = validate_email_format(email)
        if ok:
            ok, err = validate_required_text(password, 'Password', min_len=6, max_len=255)
        if ok and password != confirm_password:
            ok, err = False, 'Passwords do not match.'
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

        cur.execute("SELECT user_id FROM Users WHERE email = :e", {'e': email})
        user_id = cur.fetchone()[0]
        _issue_verification_code(cur, user_id, email, name)
        session['pending_verification_user_id'] = user_id

        flash('Almost there! Enter the code we just emailed you to verify your account.', 'success')
        return redirect(url_for('auth.verify_email'))

    return render_template('register.html')


@auth_bp.route('/verify-email', methods=['GET', 'POST'])
@limiter.limit('10 per minute')
def verify_email():
    user_id = session.get('pending_verification_user_id')
    if not user_id:
        flash('Please log in or register first.', 'error')
        return redirect(url_for('auth.login'))

    cur = get_db().cursor()
    cur.execute(
        "SELECT name, email, role, verification_code, verification_code_expires "
        "FROM Users WHERE user_id = :v_user_id",
        {'v_user_id': user_id},
    )
    row = cur.fetchone()
    if not row:
        session.pop('pending_verification_user_id', None)
        return redirect(url_for('auth.login'))
    name, email, role, stored_code, expires = row

    if request.method == 'POST':
        entered_code = request.form.get('code', '').strip()

        if not stored_code or not expires or datetime.now() > expires:
            flash('This code has expired. Request a new one below.', 'error')
        elif entered_code != stored_code:
            flash('Incorrect code. Please try again.', 'error')
        else:
            cur.execute(
                "UPDATE Users SET email_verified = 1, verification_code = NULL, "
                "verification_code_expires = NULL WHERE user_id = :v_user_id",
                {'v_user_id': user_id},
            )
            get_db().commit()
            send_welcome_email(email, name)

            session.pop('pending_verification_user_id', None)
            session.clear()
            session['user_id'] = user_id
            session['name'] = name
            session['role'] = role
            session.permanent = True

            flash('Email verified! Welcome to SmartCart.', 'success')
            return redirect(url_for('admin.dashboard') if role == 'admin' else url_for('customer.index'))

    return render_template('verify_email.html', email=email)


@auth_bp.route('/verify-email/resend', methods=['POST'])
@limiter.limit('3 per minute')
def resend_code():
    user_id = session.get('pending_verification_user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    cur = get_db().cursor()
    cur.execute("SELECT name, email FROM Users WHERE user_id = :v_user_id", {'v_user_id': user_id})
    row = cur.fetchone()
    if row:
        name, email = row
        _issue_verification_code(cur, user_id, email, name)
        flash('A new code has been sent to your email.', 'success')
    return redirect(url_for('auth.verify_email'))


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
