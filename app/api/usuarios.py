from flask import request, jsonify
from . import bp
from ..models import Usuario
from ..extensions import db
from functools import wraps
from flask_jwt_extended import get_jwt, verify_jwt_in_request

def tenant_admin_required(fn):
    """
    Decorator que restringe o acesso a rotas para administradores do tenant.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        claims = get_jwt()
        if claims.get('role') != 'admin':
            return jsonify(msg="Acesso restrito a administradores do tenant."), 403
        return fn(*args, **kwargs)
    return wrapper

@bp.route('/usuarios', methods=['GET'])
@tenant_admin_required
def list_users():
    """Lista todos os usuários do tenant atual."""
    users = Usuario.query.all()
    users_data = [
        {'id': u.id, 'login': u.login, 'nome': u.nome, 'role': u.role}
        for u in users
    ]
    return jsonify(usuarios=users_data)

@bp.route('/usuarios', methods=['POST'])
@tenant_admin_required
def create_user():
    """Cria um novo usuário no tenant atual."""
    data = request.get_json()
    if not data or not data.get('login') or not data.get('senha'):
        return jsonify(msg="Login e senha são obrigatórios."), 400

    if Usuario.query.filter_by(login=data['login']).first():
        return jsonify(msg="Este login de usuário já existe."), 409

    new_user = Usuario(
        login=data['login'],
        nome=data.get('nome'),
        role=data.get('tipo', 'usuario')
    )
    new_user.set_password(data['senha'])

    db.session.add(new_user)
    db.session.commit()

    return jsonify(sucesso=True, msg="Usuário criado com sucesso.", id=new_user.id), 201
