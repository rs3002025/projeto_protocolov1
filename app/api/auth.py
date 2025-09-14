from flask import request, jsonify
from flask_jwt_extended import create_access_token
from . import bp
from app.models import Tenant, Usuario
from app import db
from sqlalchemy import text

@bp.route('/login', methods=['POST'])
def login():
    """
    Autentica um usuário com base no client_code, login e senha.
    Retorna um JWT em caso de sucesso.
    """
    data = request.get_json()
    client_code = data.get('client_code', None)
    login_name = data.get('login', None)
    password = data.get('password', None)

    if not client_code or not login_name or not password:
        return jsonify({"msg": "Os campos 'client_code', 'login' e 'password' são obrigatórios."}), 400

    # A sessão começa no schema 'public' por padrão (configurado no before_request)
    # 1. Encontrar as informações do tenant (cliente)
    tenant = db.session.query(Tenant).filter_by(client_code=client_code).first()
    if not tenant:
        return jsonify({"msg": "Código de cliente inválido."}), 401

    schema_name = tenant.schema_name

    try:
        # 2. Mudar o search_path da sessão atual para o schema do tenant
        # O evento 'before_cursor_execute' que definimos não se aplica aqui,
        # pois ele depende do 'g.schema', que ainda não foi definido com o schema do tenant.
        # Por isso, fazemos a mudança manualmente para esta transação.
        db.session.execute(text(f'SET search_path TO "{schema_name}"'))

        # 3. Encontrar o usuário e checar a senha
        user = db.session.query(Usuario).filter_by(login=login_name).first()

        if not user or not user.check_password(password):
            # Limpa a transação e restaura o search_path
            db.session.rollback()
            db.session.execute(text('SET search_path TO public'))
            return jsonify({"msg": "Login ou senha inválidos."}), 401

        # 4. Se o login for bem-sucedido, criar o token
        additional_claims = {"schema": schema_name, "role": user.role}
        access_token = create_access_token(
            identity=user.id,
            additional_claims=additional_claims
        )

        # Restaura o search_path e finaliza a transação
        db.session.execute(text('SET search_path TO public'))
        db.session.commit()

        return jsonify(access_token=access_token)

    except Exception as e:
        db.session.rollback()
        db.session.execute(text('SET search_path TO public'))
        return jsonify({"msg": f"Erro interno durante o login: {str(e)}"}), 500
