from flask import Blueprint, render_template, redirect, url_for

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return redirect(url_for('main.login'))

@main_bp.route('/login')
def login():
    return render_template('login.html')

from app.core.search import find_protocol_across_tenants

@main_bp.route('/consulta/<int:ano>/<string:numero>')
def consulta_publica(ano, numero):
    """
    Endpoint público para consulta de protocolos via QR Code.
    """
    numero_completo = f"{numero}/{ano}"
    protocolo, tenant = find_protocol_across_tenants(numero_completo)

    # O template 'consulta.html' tratará o caso de 'protocolo' ser None.
    return render_template('consulta.html', protocolo=protocolo, tenant=tenant)

# Adicionarei mais rotas para outras páginas aqui
@main_bp.route('/menu')
def menu():
    return render_template('menu.html')

@main_bp.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@main_bp.route('/protocolo/novo')
def form():
    return render_template('form.html')

@main_bp.route('/protocolos')
def protocolos():
    return render_template('protocolos.html')

@main_bp.route('/protocolos/meus')
def meus_protocolos():
    return render_template('meus_protocolos.html')

@main_bp.route('/relatorios')
def relatorios():
    return render_template('relatorios.html')

from flask_jwt_extended import jwt_required, get_jwt

@main_bp.route('/configuracoes')
@jwt_required()
def config():
    """
    Renderiza a página de configuração apropriada com base na role do usuário.
    """
    claims = get_jwt()
    if claims.get('role') == 'super_admin':
        return render_template('admin_config.html')
    else:
        return render_template('config.html')
