from flask import Flask
from flask_login import LoginManager
from app.config import Config
from app.firebase import init_firebase

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Init Firebase
    init_firebase(app)

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
    from app.auth.routes import auth_bp
    from app.tracking.routes import tracking_bp
    from app.settings.routes import settings_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(tracking_bp)
    app.register_blueprint(settings_bp, url_prefix='/settings')

    @app.route('/')
    def index():
        from flask import render_template
        return render_template('landing.html')

    return app

from app.repos.users_repo import User
@login_manager.user_loader
def load_user(user_id):
    from app.repos.users_repo import UsersRepo
    return UsersRepo.get_by_id(user_id)
