from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy import text
from functools import wraps
from ..models import db, Tenant
from ..core.tenant_management import create_tenant_schema_and_tables

admin_bp = Blueprint('admin', __name__)

def super_admin_required(fn):
    """Decorator to protect routes that can only be accessed by a Super Admin."""
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        if claims.get('role') != 'super_admin':
            return jsonify(msg="Acesso restrito a Super Administradores."), 403
        return fn(*args, **kwargs)
    return wrapper

@admin_bp.route('/tenants', methods=['GET'])
@super_admin_required
def list_tenants():
    """Lists all tenants registered in the public schema."""
    tenants = Tenant.query.order_by(Tenant.id).all()
    return jsonify([{
        'id': t.id,
        'name': t.name,
        'client_code': t.client_code,
        'schema_name': t.schema_name,
        'is_active': t.is_active
    } for t in tenants])

@admin_bp.route('/tenants', methods=['POST'])
@super_admin_required
def create_tenant():
    """Creates a new tenant, including its schema and tables."""
    data = request.get_json()
    if not all(k in data for k in ['name', 'client_code', 'schema_name']):
        return jsonify(msg="Campos 'name', 'client_code', e 'schema_name' são obrigatórios."), 400

    try:
        new_tenant = create_tenant_schema_and_tables({
            'name': data['name'],
            'client_code': data['client_code'],
            'schema_name': data['schema_name']
        })
        if new_tenant.id is None:
             return jsonify(msg=f"Tenant com client_code '{data['client_code']}' já existe."), 409
        return jsonify(msg=f"Tenant '{data['name']}' criado com sucesso."), 201
    except ValueError as e:
        return jsonify(msg=str(e)), 409
    except Exception as e:
        current_app.logger.error(f"Erro ao criar tenant: {e}")
        db.session.rollback()
        return jsonify(msg="Erro interno ao criar tenant."), 500

@admin_bp.route('/tenants/<int:tenant_id>', methods=['DELETE'])
@super_admin_required
def delete_tenant(tenant_id):
    """Deletes a tenant and its associated schema."""
    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        return jsonify(msg="Tenant não encontrado."), 404

    schema_name = tenant.schema_name

    try:
        db.session.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        db.session.delete(tenant)
        db.session.commit()
        return jsonify(msg=f"Tenant '{tenant.name}' e todos os seus dados foram excluídos com sucesso.")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao excluir tenant: {e}")
        return jsonify(msg="Erro interno ao excluir tenant."), 500
