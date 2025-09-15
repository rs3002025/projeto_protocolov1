from flask import Flask
from .config import Config
from sqlalchemy import event
from .core.tenancy import set_schema_on_execute
from .extensions import db, jwt

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    jwt.init_app(app)

    # Com a app inicializada, agora é seguro registrar o listener do SQLAlchemy
    with app.app_context():
        event.listen(db.engine, "before_cursor_execute", set_schema_on_execute)

    # Registrar blueprints
    from app.api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    from app.api.admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/api/admin')

    from .main import main_bp
    app.register_blueprint(main_bp)

    @app.route('/')
    def index():
        return "API do Sistema de Protocolo"

    return app
