from functools import wraps

from flask import flash, redirect, request, url_for

from auth_tokens import current_user_id, current_user_role
from db import get_db


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user_id() is None:
            return redirect(url_for('auth.login', next=request.full_path))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = current_user_id()
        if user_id is None or current_user_role() != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('auth.login', next=request.full_path))

        # The token carries the role it was minted with, so a revoked admin
        # would keep access until it expired. Admin is high-value enough to
        # re-check against the database on every request.
        cur = get_db().cursor()
        cur.execute("SELECT role FROM Users WHERE user_id = :v_user_id", {'v_user_id': user_id})
        row = cur.fetchone()
        if not row or row[0] != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('auth.login', next=request.full_path))
        return f(*args, **kwargs)
    return decorated
