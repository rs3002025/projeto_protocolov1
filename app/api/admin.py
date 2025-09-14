from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt
from . import bp as api_bp  # Import the main api blueprint to create a new one for admin
from ..models import Tenant
from ..extensions import db

# Decorator para proteger rotas de Super Admin
def super_admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        claims = get_jwt()
        if claims.get('role') != 'super_admin':
            return jsonify(msg="Acesso restrito a Super Administradores."), 403
        return fn(*args, **kwargs)
    return wrapper

# Criar um novo Blueprint para as rotas de admin, aninhado sob /api/admin
# Note: This is a conceptual approach. In Flask, you register blueprints on the app, not on other blueprints.
# I will create a new blueprint and register it on the app with the `/api/admin` prefix.
# For now, I will just define the routes and create the blueprint object.

from flask import Blueprint

admin_bp = Blueprint('admin_api', __name__)

@admin_bp.route('/tenants', methods=['GET'])
@super_admin_required
def list_tenants():
    """
    Lista todos os tenants cadastrados no sistema.
    Acessível apenas por Super Admin.
    """
    tenants = Tenant.query.all()
    tenants_data = [
        {
            'id': tenant.id,
            'name': tenant.name,
            'client_code': tenant.client_code,
            'schema_name': tenant.schema_name,
            'is_active': tenant.is_active,
            'created_at': tenant.created_at.isoformat()
        } for tenant in tenants
    ]
    return jsonify(tenants_data)

@admin_bp.route('/tenants/<int:tenant_id>', methods=['PUT'])
@super_admin_required
def update_tenant(tenant_id):
    """
    Atualiza os detalhes de um tenant (nome, status de ativação).
    Acessível apenas por Super Admin.
    """
    tenant = Tenant.query.get_or_404(tenant_id)
    data = request.get_json()

    if 'name' in data:
        tenant.name = data['name']

    if 'is_active' in data:
        if not isinstance(data['is_active'], bool):
            return jsonify(msg="'is_active' deve ser um valor booleano (true/false)."), 400
        tenant.is_active = data['is_active']

    db.session.commit()

    updated_tenant_data = {
        'id': tenant.id,
        'name': tenant.name,
        'client_code': tenant.client_code,
        'schema_name': tenant.schema_name,
        'is_active': tenant.is_active,
        'created_at': tenant.created_at.isoformat()
    }
    return jsonify(updated_tenant_data)

from flask import request
from app.core.tenant_management import create_tenant_schema_and_tables

@admin_bp.route('/tenants', methods=['POST'])
@super_admin_required
def create_tenant():
    """
    Cria um novo tenant (cliente), incluindo seu schema e tabelas.
    Acessível apenas por Super Admin.
    """
    data = request.get_json()
    name = data.get('name')
    client_code = data.get('client_code')
    schema_name = data.get('schema_name')

    if not all([name, client_code, schema_name]):
        return jsonify(msg="Os campos 'name', 'client_code' e 'schema_name' são obrigatórios."), 400

    try:
        tenant_info = {'name': name, 'client_code': client_code, 'schema_name': schema_name}
        new_tenant = create_tenant_schema_and_tables(tenant_info)

        if new_tenant.id is None: # Se o tenant já existia
            return jsonify(msg=f"Tenant com client_code '{client_code}' já existe."), 409

        tenant_data = {
            'id': new_tenant.id,
            'name': new_tenant.name,
            'client_code': new_tenant.client_code,
            'schema_name': new_tenant.schema_name,
        }
        return jsonify(tenant_data), 201
    except Exception as e:
        db.session.rollback()
        return jsonify(msg=f"Erro ao criar tenant: {str(e)}"), 500
