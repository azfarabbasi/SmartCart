"""Stateless JWT auth, carried in an httpOnly cookie.

Identity lives in a signed token rather than a server-side session, so any
instance can verify a request on its own -- which matters on serverless,
where consecutive requests hit different instances.

The token is sent as an httpOnly cookie rather than being kept in
localStorage: the browser attaches it automatically (so server-rendered
pages know who you are on the very first request, before any JS runs), and
page scripts can't read it, so an XSS bug can't exfiltrate a login.

Flask's own session is still used, but only for transient non-identity
state: flash messages, the pending email-verification id, stock alerts.
"""
import datetime

import jwt
from flask import current_app, g, request

COOKIE_NAME = 'sc_auth'
ALGORITHM = 'HS256'


def issue_token(user_id, name, role):
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        'sub': str(user_id),
        'name': name,
        'role': role,
        'iat': now,
        'exp': now + current_app.config['JWT_LIFETIME'],
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm=ALGORITHM)


def decode_token(token):
    try:
        return jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None  # expired, tampered with, or signed by a rotated key


def set_auth_cookie(response, token):
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        secure=bool(current_app.config.get('SESSION_COOKIE_SECURE')),
        samesite='Lax',
        max_age=int(current_app.config['JWT_LIFETIME'].total_seconds()),
        path='/',
    )
    return response


def clear_auth_cookie(response):
    response.delete_cookie(COOKIE_NAME, path='/')
    return response


def load_current_user():
    """Populate g.current_user from the cookie. Registered as before_request."""
    g.current_user = None
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return
    payload = decode_token(token)
    if not payload:
        return
    try:
        g.current_user = {
            'user_id': int(payload['sub']),
            'name': payload.get('name'),
            'role': payload.get('role'),
        }
    except (KeyError, TypeError, ValueError):
        g.current_user = None


def current_user():
    return g.get('current_user')


def current_user_id():
    user = g.get('current_user')
    return user['user_id'] if user else None


def current_user_name():
    user = g.get('current_user')
    return user['name'] if user else None


def current_user_role():
    user = g.get('current_user')
    return user['role'] if user else None
