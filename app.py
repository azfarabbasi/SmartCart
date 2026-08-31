import os
import traceback

from flask import Flask, jsonify, render_template

import auth_tokens
import db
import security
from config import get_config
from extensions import csrf, limiter


def create_app():
    app = Flask(__name__)
    app.config.from_object(get_config())

    for folder in (
        app.config['UPLOAD_FOLDER'],
        app.config['FEEDBACK_UPLOAD_FOLDER'],
        app.config['PAYMENT_PROOF_UPLOAD_FOLDER'],
    ):
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError:
            pass  # Read-only filesystem (Vercel)

    try:
        db.init_pool(app)
    except Exception as e:
        app.logger.error(f'DB pool init failed: {e}')
        app._db_init_error = str(e)

    app.teardown_appcontext(db.close_db)

    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

    csrf.init_app(app)
    limiter.init_app(app)
    security.register_security_headers(app)

    # Identity comes from a signed cookie, decoded once per request.
    app.before_request(auth_tokens.load_current_user)

    @app.context_processor
    def inject_current_user():
        return {'current_user': auth_tokens.current_user()}

    from slugs import slugify as _slugify
    from flask import has_request_context, url_for

    def media_url(path):
        if not path:
            return ''
        path_str = str(path).strip()
        if path_str.startswith('data:') or path_str.startswith('http://') or path_str.startswith('https://') or path_str.startswith('/'):
            return path_str
        if has_request_context():
            return url_for('static', filename=path_str)
        return f'/static/{path_str}'

    from whatsapp_utils import format_whatsapp_phone, get_whatsapp_order_link

    app.jinja_env.globals['min'] = min
    app.jinja_env.globals['max'] = max
    app.jinja_env.globals['slugify'] = _slugify
    app.jinja_env.globals['media_url'] = media_url
    app.jinja_env.filters['media_url'] = media_url
    app.jinja_env.globals['format_whatsapp_phone'] = format_whatsapp_phone
    app.jinja_env.globals['get_whatsapp_order_link'] = get_whatsapp_order_link

    # Stamp written by build_assets.py; appended to the bundle URLs so a new
    # deploy is never served from a stale browser cache.
    try:
        version_file = os.path.join(app.static_folder, 'dist', 'version.txt')
        with open(version_file, encoding='utf-8') as fh:
            app.config['ASSET_VERSION'] = fh.read().strip()
    except OSError:
        app.config['ASSET_VERSION'] = 'dev'

    @app.context_processor
    def inject_asset_version():
        if app.config.get('DEBUG'):
            try:
                version_file = os.path.join(app.static_folder, 'dist', 'version.txt')
                with open(version_file, encoding='utf-8') as fh:
                    return {'asset_version': fh.read().strip()}
            except OSError:
                pass
        return {'asset_version': app.config.get('ASSET_VERSION', 'dev')}

    from cache_service import (get_nav_categories as _cached_nav_categories,
                               get_site_settings as _cached_site_settings)

    @app.context_processor
    def inject_site_settings():
        settings = _cached_site_settings()
        return {
            'site_settings': settings,
            'contact_phone': settings.get('contact_phone') or app.config['CONTACT_PHONE'],
            'contact_email': settings.get('contact_email') or app.config['CONTACT_EMAIL'],
            'whatsapp_number': settings.get('whatsapp_number') or app.config['WHATSAPP_NUMBER'],
        }

    @app.context_processor
    def inject_nav_categories():
        return {'nav_categories': _cached_nav_categories()}

    import gzip
    from flask import request

    @app.after_request
    def optimize_response_headers_and_compression(response):
        # 1. Long-term browser caching for static assets
        if request.path.startswith('/static/dist/'):
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        elif request.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'public, max-age=86400'

        # 2. Gzip compression for text / json / svg / css / js responses
        accept_encoding = request.headers.get('Accept-Encoding', '')
        if (
            'gzip' in accept_encoding
            and response.status_code == 200
            and not response.headers.get('Content-Encoding')
            and response.mimetype in (
                'text/html', 'text/css', 'text/javascript', 'application/javascript',
                'application/json', 'image/svg+xml', 'text/plain', 'text/xml'
            )
        ):
            try:
                response.direct_passthrough = False
                response_data = response.get_data()
                if len(response_data) > 500:
                    compressed_data = gzip.compress(response_data, compresslevel=6)
                    response.set_data(compressed_data)
                    response.headers['Content-Encoding'] = 'gzip'
                    response.headers['Content-Length'] = len(compressed_data)
                    response.headers['Vary'] = 'Accept-Encoding'
            except Exception:
                pass

        return response

    from flask_wtf.csrf import CSRFError
    from flask import flash, redirect, request, url_for

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        app.logger.warning(f"CSRF error caught on {request.path}: {e.description}")
        flash('Your session or security token expired. Please try submitting again.', 'error')
        referrer = request.referrer
        if referrer and referrer.startswith(request.host_url):
            return redirect(referrer)
        return redirect(url_for('customer.index'))

    @app.errorhandler(500)
    def internal_error(e):
        # Stack traces name internal paths, SQL and config, so they go to the
        # server log only. They were being returned to the browser while
        # debugging the Vercel deploy -- fine there, not on a live shop.
        app.logger.error('Unhandled error: %s\n%s', e, traceback.format_exc())
        if app.config.get('DEBUG'):
            return jsonify({
                'error': str(e),
                'db_init_error': getattr(app, '_db_init_error', None),
                'traceback': traceback.format_exc(),
            }), 500
        return render_template('error.html', code=500), 500

    @app.errorhandler(404)
    def not_found(_e):
        return render_template('error.html', code=404), 404

    from blueprints.admin import admin_bp
    from blueprints.analytics import analytics_bp
    from blueprints.auth import auth_bp
    from blueprints.customer import customer_bp
    from blueprints.feedback import feedback_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(feedback_bp)

    return app


app = create_app()

import logging
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=app.config['DEBUG'])
