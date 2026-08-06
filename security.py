from flask import flash, redirect, request, url_for

FAILED_LOGIN_THRESHOLD = 5
LOCKOUT_MINUTES = 15


def register_security_headers(app):
    @app.after_request
    def set_headers(resp):
        resp.headers['X-Content-Type-Options'] = 'nosniff'
        resp.headers['X-Frame-Options'] = 'DENY'
        resp.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        resp.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "font-src https://cdn.jsdelivr.net; "
            "media-src 'self'; "
            "connect-src 'self'"
        )
        if app.config.get('SESSION_COOKIE_SECURE'):
            resp.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return resp

    @app.errorhandler(413)
    def too_large(_e):
        flash('That file is too large to upload.', 'error')
        return redirect(request.referrer or url_for('customer.index')), 302


def log_admin_action(cur, admin_user_id, action, target_type=None, target_id=None, details=None):
    cur.execute(
        """
        INSERT INTO AdminAuditLog (audit_id, admin_user_id, action, target_type, target_id,
                                    details, ip_address, created_at)
        VALUES (adminauditlog_seq.NEXTVAL, :uid, :act, :ttype, :tid, :det, :ip, SYSDATE)
        """,
        {
            'uid': admin_user_id,
            'act': action,
            'ttype': target_type,
            'tid': target_id,
            'det': details,
            'ip': request.remote_addr,
        },
    )


def record_login_attempt(cur, email, success):
    cur.execute(
        """
        INSERT INTO LoginAttempts (attempt_id, email, ip_address, success, attempted_at)
        VALUES (loginattempts_seq.NEXTVAL, :e, :ip, :s, SYSDATE)
        """,
        {'e': email.lower(), 'ip': request.remote_addr, 's': 1 if success else 0},
    )
    if success:
        cur.execute("DELETE FROM LoginAttempts WHERE LOWER(email) = :e AND success = 0", {'e': email.lower()})


def is_locked_out(cur, email):
    cur.execute(
        """
        SELECT COUNT(*) FROM LoginAttempts
        WHERE LOWER(email) = :e AND success = 0
          AND attempted_at > SYSDATE - (:mins / 1440)
        """,
        {'e': email.lower(), 'mins': LOCKOUT_MINUTES},
    )
    return cur.fetchone()[0] >= FAILED_LOGIN_THRESHOLD
