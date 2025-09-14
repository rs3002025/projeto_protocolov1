from flask import Flask, g, request
from .config import Config
from sqlalchemy import event
from .core.tenancy import set_schema_on_execute
from .extensions import db, jwt
from flask_jwt_extended import verify_jwt_in_request, get_jwt

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    jwt.init_app(app)

    @app.before_request
    def before_request_handler():
        """
        Executado antes de cada requisição.
        Verifica o JWT (se presente) e define o search_path do banco de dados.
        """
        g.schema = 'public'
        # Rotas que não exigem verificação de JWT ou manipulação de schema de tenant
        public_endpoints = ['main.login', 'main.consulta_publica', 'api.login']
        if request.endpoint in public_endpoints:
            return

        # Para rotas da API, verifica o JWT e tenta definir o schema
        if request.path.startswith('/api/'):
            try:
                verify_jwt_in_request()
                claims = get_jwt()
                g.schema = claims.get('schema', 'public')
            except Exception:
                # Se o token for inválido ou ausente, a exceção será lançada
                # e o Flask-JWT-Extended retornará um erro 401.
                # O g.schema permanecerá 'public', o que é seguro.
                pass

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

    return app
