import os

from flask import Flask

import db
import security
from config import get_config
from extensions import csrf, limiter


def create_app():
    app = Flask(__name__)
    app.config.from_object(get_config())

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['FEEDBACK_UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['PAYMENT_PROOF_UPLOAD_FOLDER'], exist_ok=True)

    db.init_pool(app)
    app.teardown_appcontext(db.close_db)

    csrf.init_app(app)
    limiter.init_app(app)
    security.register_security_headers(app)

    app.jinja_env.globals['min'] = min
    app.jinja_env.globals['max'] = max

    @app.context_processor
    def inject_contact_info():
        return {
            'contact_phone': app.config['CONTACT_PHONE'],
            'contact_email': app.config['CONTACT_EMAIL'],
            'whatsapp_number': app.config['WHATSAPP_NUMBER'],
        }

    @app.context_processor
    def inject_nav_categories():
        from flask import g
        if 'nav_categories' not in g:
            try:
                cur = db.get_db().cursor()
                cur.execute(
                    "SELECT category_id, category_name FROM ("
                    "  SELECT category_id, category_name FROM Categories ORDER BY category_name"
                    ") WHERE ROWNUM <= 12"
                )
                g.nav_categories = cur.fetchall()
            except Exception:
                g.nav_categories = []
        return {'nav_categories': g.nav_categories}

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
