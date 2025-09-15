from flask import Blueprint, g, request, jsonify
from flask_jwt_extended import get_jwt, verify_jwt_in_request
from app.core.tenancy import set_tenant_schema_for_request

bp = Blueprint('api', __name__)

@bp.before_request
def before_request_handler():
    """
    Handler executado antes de cada request no blueprint 'api'.
    Ele verifica o JWT e configura o schema do tenant para a request.
    """
    # A rota de login é pública e não precisa de JWT.
    # Ela será tratada como um caso especial dentro de sua própria lógica.
    if request.endpoint and 'login' in request.endpoint:
        set_tenant_schema_for_request('public') # Começa no public para achar o tenant
        return

    # Para todas as outras rotas, exigimos e verificamos um JWT.
    try:
        verify_jwt_in_request()
        claims = get_jwt()
        schema = claims.get('schema')
        if not schema:
            return jsonify({"msg": "Token JWT inválido: 'schema' ausente."}), 401

        # Define o schema para a duração desta request
        set_tenant_schema_for_request(schema)

    except Exception as e:
        # A exceção de JWT inválido será tratada pelo Flask-JWT-Extended,
        # resultando em um erro 401 Unauthorized.
        # Se chegar aqui, é um erro inesperado.
        return jsonify({"msg": f"Erro interno ao processar token: {str(e)}"}), 500

# Importar as rotas no final para evitar importação circular.
from . import auth
# Futuramente: from . import protocolos, usuarios, etc.
