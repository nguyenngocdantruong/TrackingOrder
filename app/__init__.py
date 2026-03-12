import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask
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

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(link_bp)
    app.register_blueprint(tracking_bp)
    app.register_blueprint(settings_bp, url_prefix='/settings')
    app.register_blueprint(payments_bp, url_prefix='/payments')

    @app.route('/')
    def index():
        from flask import render_template
        providers_for_landing = [
            {"id": provider_id, "name": display_name}
            for provider_id, display_name in registry.list_providers()
        ]
        return render_template('landing.html', providers=providers_for_landing)

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
    return UsersRepo.get_by_id(user_id)
