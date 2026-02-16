from flask import Flask
from pathlib import Path

from .extensions import db, login_manager
from .models import User
from config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # init extensions
    db.init_app(app)
    login_manager.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # ✅ Ensure upload folders exist
    upload_root = Path(app.config["UPLOAD_FOLDER"])
    (upload_root / app.config["SALON_UPLOAD_SUBDIR"]).mkdir(parents=True, exist_ok=True)
    (upload_root / app.config["STAFF_UPLOAD_SUBDIR"]).mkdir(parents=True, exist_ok=True)

    # register blueprints
    from .auth.routes import auth_bp
    from .main.routes import main_bp
    from .owner.routes import owner_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(owner_bp)

    # create db tables (MVP)
    with app.app_context():
        db.create_all()

    return app
