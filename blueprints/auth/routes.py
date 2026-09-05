import random
from datetime import datetime, timedelta
import requests as _requests

from flask import (Blueprint, current_app, flash, make_response, redirect,
                    render_template, request, session, url_for)

from auth_tokens import clear_auth_cookie, issue_token, set_auth_cookie
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


def _mask_email(email):
    """Mask email for privacy and log hygiene (e.g. az***@gmail.com)."""
    if not email or '@' not in email:
        return '[REDACTED]'
    user, domain = email.split('@', 1)
    masked_user = user[:2] + '***' if len(user) > 2 else '***'
    return f"{masked_user}@{domain}"


def _send_via_resend(to_email, subject, body_html, to_name='Customer'):
    """Send email via Resend API (100% free, 3000 emails/mo, works on Vercel)."""
    api_key = current_app.config.get('RESEND_API_KEY', '').strip()
    if not api_key:
        return False
    from_email = current_app.config.get('RESEND_FROM_EMAIL', 'SmartCart <onboarding@resend.dev>')
    try:
        resp = _requests.post(
            'https://api.resend.com/emails',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'from': from_email,
                'to': [to_email],
                'subject': subject,
                'html': body_html,
            },
            timeout=15,
        )
        if resp.status_code in (200, 201):
            current_app.logger.info(f'Resend email sent successfully to {_mask_email(to_email)}')
            return True
        current_app.logger.warning(f'Resend send failed {resp.status_code}: {resp.text[:200]}')
        return False
    except Exception as e:
        current_app.logger.warning(f'Resend request error: {e}')
        return False


def _send_via_brevo(to_email, subject, body_html, to_name='Customer'):
    """Send email via Brevo API (works on Vercel - no SMTP ports needed)."""
    api_key = current_app.config.get('BREVO_API_KEY', '').strip()
    if not api_key:
        return False
    sender_email = current_app.config.get('BREVO_SENDER_EMAIL') or current_app.config.get('EMAIL_USER', '')
    sender_name = current_app.config.get('BREVO_SENDER_NAME', 'SmartCart')
    try:
        resp = _requests.post(
            'https://api.brevo.com/v3/smtp/email',
            headers={
                'api-key': api_key,
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            json={
                'sender': {'name': sender_name, 'email': sender_email},
                'to': [{'email': to_email, 'name': to_name or 'Customer'}],
                'subject': subject,
                'htmlContent': body_html,
            },
            timeout=15,
        )
        if resp.status_code in (200, 201):
            current_app.logger.info(f'Brevo email sent successfully to {_mask_email(to_email)}')
            return True
        current_app.logger.warning(f'Brevo send failed {resp.status_code}: {resp.text[:200]}')
        return False
    except Exception as e:
        current_app.logger.warning(f'Brevo request error: {e}')
        return False


def _send_via_smtp(to_email, subject, body_html):
    """Send email via raw SMTP (works locally, blocked on Vercel)."""
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = current_app.config['EMAIL_USER']
        msg['To'] = to_email
        msg.attach(MIMEText(body_html, 'html'))
        server = smtplib.SMTP(current_app.config['EMAIL_HOST'], current_app.config['EMAIL_PORT'], timeout=10)
        server.starttls()
        server.login(current_app.config['EMAIL_USER'], current_app.config['EMAIL_PASSWORD'])
        server.sendmail(current_app.config['EMAIL_USER'], to_email, msg.as_string())
        server.quit()
        current_app.logger.info(f'SMTP email sent successfully to {_mask_email(to_email)}')
        return True
    except Exception as e:
        current_app.logger.warning(f'SMTP send failed: {e}')
        return False


def _send_email(to_email, subject, body_html, to_name='Customer'):
    """Send email trying Resend -> Brevo -> SMTP."""
    # 1. Try Resend (100% Free, 3,000 emails/mo)
    if current_app.config.get('RESEND_API_KEY'):
        ok = _send_via_resend(to_email, subject, body_html, to_name=to_name)
        if ok:
            return True
        current_app.logger.warning(f'Resend failed, trying other providers for: {subject}')
    # 2. Try Brevo
    if current_app.config.get('BREVO_API_KEY'):
        ok = _send_via_brevo(to_email, subject, body_html, to_name=to_name)
        if ok:
            return True
        current_app.logger.warning(f'Brevo failed, falling back to SMTP for: {subject}')
    # 3. Fall back to SMTP (works locally)
    return _send_via_smtp(to_email, subject, body_html)


def send_welcome_email(to_email, name):
    body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f5; padding: 20px; color: #333;">
        <div style="max-width: 500px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.05); padding: 30px;">
            <h2 style="color: #f59e0b; margin-top: 0;">Welcome to SmartCart!</h2>
            <p>Hi <strong>{name}</strong>,</p>
            <p>Your email is verified and your <strong>SmartCart</strong> account is ready to go.</p>
            <p>You can now log in and explore our collection of premium electronics.</p>
            <br>
            <p style="color: #6b7280; font-size: 14px; margin-bottom: 0;">&mdash; The SmartCart Team</p>
        </div>
    </body>
    </html>
    """
    _send_email(to_email, 'Welcome to SmartCart!', body, to_name=name)


def send_verification_email(to_email, name, code):
    body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f5; padding: 20px; color: #333;">
        <div style="max-width: 500px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.05); padding: 30px; text-align: center;">
            <h2 style="color: #f59e0b; margin-top: 0;">Verify Your SmartCart Account</h2>
            <p style="color: #4b5563;">Hi <strong>{name}</strong>, please use the following 6-digit verification code to complete your registration:</p>
            <div style="margin: 25px 0; background: #fef3c7; border: 2px dashed #f59e0b; border-radius: 8px; padding: 15px;">
                <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #b45309; font-family: monospace;">{code}</span>
            </div>
            <p style="color: #6b7280; font-size: 13px;">This code expires in {CODE_VALID_MINUTES} minutes. If you did not sign up for SmartCart, please ignore this email.</p>
            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
            <p style="color: #9ca3af; font-size: 12px; margin-bottom: 0;">&mdash; The SmartCart Team</p>
        </div>
    </body>
    </html>
    """
    return _send_email(to_email, 'Verify your SmartCart account', body, to_name=name)


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

        # Fallback alias matching for admin accounts
        if not user and email.lower() in ('admin@smart.com', 'admin@smartcart.com'):
            cur.execute(
                "SELECT user_id, name, password, role, email_verified FROM Users WHERE LOWER(email) IN ('admin@smartcart.com', 'admin@smart.com')"
            )
            user = cur.fetchone()

        ok = False
        if user:
            stored_pw = user[2] or ''
            try:
                ok = check_password_hash(stored_pw, password)
            except Exception:
                ok = False

            # Backward compatibility for plain-text passwords (auto-migrates to secure hash)
            if not ok and stored_pw and len(stored_pw) >= 6 and stored_pw == password:
                ok = True
                cur.execute(
                    "UPDATE Users SET password = :p, email_verified = 1 WHERE user_id = :p_uid",
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
            session.pop('pending_verification_user_id', None)
            if next_url:
                destination = next_url
            elif user[3] == 'admin':
                destination = url_for('admin.dashboard')
            else:
                destination = url_for('customer.index')
            response = make_response(redirect(destination))
            return set_auth_cookie(response, issue_token(user[0], user[1], user[3]))

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

            flash('Email verified! Welcome to SmartCart.', 'success')
            destination = url_for('admin.dashboard') if role == 'admin' else url_for('customer.index')
            response = make_response(redirect(destination))
            return set_auth_cookie(response, issue_token(user_id, name, role))

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
    return clear_auth_cookie(make_response(redirect(url_for('auth.login'))))
