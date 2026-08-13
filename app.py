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

    csrf.init_app(app)
    limiter.init_app(app)
    security.register_security_headers(app)

    # Identity comes from a signed cookie, decoded once per request.
    app.before_request(auth_tokens.load_current_user)

    @app.context_processor
    def inject_current_user():
        return {'current_user': auth_tokens.current_user()}

    from slugs import slugify as _slugify

    app.jinja_env.globals['min'] = min
    app.jinja_env.globals['max'] = max
    app.jinja_env.globals['slugify'] = _slugify

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
        return {'asset_version': app.config['ASSET_VERSION']}

    @app.context_processor
    def inject_site_settings():
        from flask import g

        import sitesettings
        if 'site_settings' not in g:
            try:
                cur = db.get_db().cursor()
                g.site_settings = sitesettings.get_settings(cur)
            except Exception:
                g.site_settings = dict(sitesettings.DEFAULTS)
        settings = g.site_settings
        return {
            'site_settings': settings,
            'contact_phone': settings.get('contact_phone') or app.config['CONTACT_PHONE'],
            'contact_email': settings.get('contact_email') or app.config['CONTACT_EMAIL'],
            'whatsapp_number': settings.get('whatsapp_number') or app.config['WHATSAPP_NUMBER'],
        }

    @app.context_processor
    def inject_nav_categories():
        from flask import g

        from slugs import slugify
        if 'nav_categories' not in g:
            try:
                cur = db.get_db().cursor()
                # DISTINCT by name: the catalog can hold several rows sharing a
                # display name, and the nav should show that category once.
                cur.execute(
                    "SELECT category_name FROM ("
                    "  SELECT DISTINCT category_name FROM Categories ORDER BY category_name"
                    ") WHERE ROWNUM <= 12"
                )
                g.nav_categories = [
                    {'name': row[0], 'slug': slugify(row[0])} for row in cur.fetchall()
                ]
            except Exception:
                g.nav_categories = []
        return {'nav_categories': g.nav_categories}

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

if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'])

