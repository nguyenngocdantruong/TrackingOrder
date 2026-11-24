import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask, redirect, request, send_from_directory, url_for
from werkzeug.exceptions import HTTPException
from flask_login import LoginManager
from app.config import Config
from app.firebase import init_firebase
from app.payments.registry import init_gateways
from app.notifications.registry import init_notification_providers

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    _configure_logging(app)

    # Init Firebase
    init_firebase(app)

    # Init payment gateways
    init_gateways(app)

    # Init notification providers
    init_notification_providers(app)

    # Init extensions
    login_manager.init_app(app)

    # Context processors / filters
    from app.providers.registry import registry
    @app.template_filter('format_provider_time')
    def format_provider_time(dt, carrier_id):
        provider = registry.get_provider(carrier_id)
        if provider:
            return provider.format_time(dt)
        return dt.strftime("%H:%M %d/%m/%Y") if dt else "N/A"

    # Register blueprints
    from app.auth.routes import auth_bp, link_bp
    from app.tracking.routes import tracking_bp
    from app.settings.routes import settings_bp
    from app.payments.routes import payments_bp
    from app.api import api_bp
    from app.v2 import v2_bp

    from app.admin import admin_bp, is_admin
    from app.admin_operations import admin_ops
    app.context_processor(lambda: {'is_system_admin': is_admin()})

    # Primary Frontend (/) + Partner REST API (/api/v1)
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    app.register_blueprint(v2_bp)
    app.register_blueprint(admin_ops)

    # Legacy Frontend (/v1/*)
    app.register_blueprint(admin_bp, url_prefix='/v1/admin')
    app.register_blueprint(auth_bp, url_prefix='/v1/auth')
    app.register_blueprint(link_bp, url_prefix='/v1')
    app.register_blueprint(tracking_bp, url_prefix='/v1')
    app.register_blueprint(settings_bp, url_prefix='/v1/settings')
    app.register_blueprint(payments_bp, url_prefix='/v1/payments')

    @app.route('/v1', endpoint='index')
    @app.route('/v1/', endpoint='index')
    def v1_index():
        from flask import render_template
        providers_for_landing = [
            {"id": provider_id, "name": display_name}
            for provider_id, display_name in registry.list_providers()
        ]
        return render_template('landing.html', providers=providers_for_landing)

    @app.route('/favicon.ico')
    def favicon():
        return send_from_directory(app.static_folder, 'favicon.svg', mimetype='image/svg+xml')

    @app.route('/manifest.webmanifest')
    def pwa_manifest():
        return send_from_directory(
            app.static_folder,
            'manifest.webmanifest',
            mimetype='application/manifest+json',
        )

    @app.route('/sw.js')
    def service_worker():
        resp = send_from_directory(
            app.static_folder,
            'sw.js',
            mimetype='application/javascript',
        )
        resp.headers['Service-Worker-Allowed'] = '/'
        resp.headers['Cache-Control'] = 'no-cache'
        return resp

    @app.route('/v2')
    @app.route('/v2/')
    def legacy_v2_root_redirect():
        qs = f'?{request.query_string.decode()}' if request.query_string else ''
        return redirect('/' + qs)

    @app.route('/v2/<path:subpath>')
    def legacy_v2_subpath_redirect(subpath: str):
        qs = f'?{request.query_string.decode()}' if request.query_string else ''
        return redirect(f'/{subpath}{qs}')

    @login_manager.unauthorized_handler
    def handle_unauthorized():
        next_target = request.full_path.rstrip('?')
        if request.path.startswith('/v1'):
            return redirect(url_for('auth.login', next=next_target))
        return redirect(url_for('v2.login', next=next_target))

    @app.errorhandler(HTTPException)
    def handle_http_exception(err: HTTPException):
        if err.code >= 500:
            app.logger.exception("HTTP %s error", err.code, exc_info=err)
        else:
            app.logger.warning("HTTP %s error: %s", err.code, err.description)
        return err

    @app.errorhandler(Exception)
    def handle_unexpected_exception(err: Exception):
        app.logger.exception("Unhandled exception", exc_info=err)
        from flask import jsonify
        return jsonify({'error': 'Internal Server Error'}), 500

    return app


def _configure_logging(app: Flask):
    log_file = app.config.get('LOG_FILE', 'logs/app.log')
    log_level_name = str(app.config.get('LOG_LEVEL', 'INFO')).upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    app.logger.setLevel(log_level)

    try:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        if not any(isinstance(h, RotatingFileHandler) and getattr(h, 'baseFilename', None) == os.path.abspath(log_file) for h in app.logger.handlers):
            file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding='utf-8')
            file_handler.setLevel(log_level)
            formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
            file_handler.setFormatter(formatter)
            app.logger.addHandler(file_handler)
    except Exception as exc:
        app.logger.warning("Failed to set up file logging: %s", exc)

    logging.getLogger('werkzeug').setLevel(log_level)

from app.repos.users_repo import User
@login_manager.user_loader
def load_user(user_id):
    from app.repos.users_repo import UsersRepo
    user = UsersRepo.get_by_id(user_id)
    return user if user and user.is_active else None
