from flask import request, jsonify, current_app
from flask_jwt_extended import create_access_token
from . import bp
from ..models import Tenant, Usuario
from ..extensions import db
from sqlalchemy import text

@bp.route('/login', methods=['POST'])
def login():
    """
    Autentica um usuário com base no client_code, login e senha.
    Se client_code for vazio, tenta autenticar como Super Admin.
    Retorna um JWT em caso de sucesso.
    """
    data = request.get_json()
    client_code = data.get('client_code', '')
    login_name = data.get('login', None)
    password = data.get('password', None)

    if not login_name or not password:
        return jsonify({"msg": "Os campos 'login' e 'password' são obrigatórios."}), 400

    # --- Lógica do Super Admin ---
    if not client_code:
        sa_login = current_app.config['SUPER_ADMIN_LOGIN']
        sa_password = current_app.config['SUPER_ADMIN_PASSWORD']
        if login_name == sa_login and password == sa_password:
            additional_claims = {"role": "super_admin"}
            access_token = create_access_token(
                identity='super_admin',
                additional_claims=additional_claims
            )
            return jsonify(access_token=access_token)
        else:
            return jsonify({"msg": "Credenciais de Super Admin inválidas."}), 401

    # --- Lógica do Tenant (usuário normal) ---
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
        additional_claims = {"schema": schema_name, "role": user.role, "login": user.login}
        access_token = create_access_token(
            identity=user.id, # A identidade principal do token é o ID do usuário
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
