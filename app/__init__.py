from flask import Flask
from .config import Config
from sqlalchemy import event
from .core.tenancy import set_schema_on_execute
from .extensions import db, jwt

from flask import g, request
from flask_jwt_extended import get_jwt, verify_jwt_in_request

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    jwt.init_app(app)

    @app.before_request
    def before_request_handler():
        g.schema = 'public'
        # As rotas de frontend não são protegidas por JWT diretamente,
        # mas as chamadas de API que elas fazem são.
        # A exceção é a rota de login da API.
        if request.path.startswith('/api/') and not request.path.startswith('/api/login'):
            try:
                verify_jwt_in_request()
                claims = get_jwt()
                g.schema = claims.get('schema', 'public')
            except Exception as e:
                # Deixa o Flask-JWT-Extended lidar com o erro de token inválido/ausente.
                # O schema permanecerá 'public', o que é seguro.
                pass

    with app.app_context():
        event.listen(db.engine, "before_cursor_execute", set_schema_on_execute)

    from app.api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    from app.api.admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/api/admin')

    from .main import main_bp
    app.register_blueprint(main_bp)

    return app
