import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# --- Configuration ---
SECRET_KEY = os.getenv('SECRET_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')

if not SECRET_KEY or not DATABASE_URL:
    raise RuntimeError("SECRET_KEY and DATABASE_URL must be set in the environment or a .env file.")

app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True, 'pool_recycle': 300}
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.getenv('COOKIE_SECURE', 'true').lower() == 'true'
app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024

# --- Extensions Initialization ---
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
csrf = CSRFProtect(app)

# --- Flask-Login Configuration ---
# 'login' is the function name of the route for the login page
login_manager.login_view = 'login'
# 'info' is a bootstrap class for message flashing
login_manager.login_message_category = 'info'
login_manager.login_message = 'Faça login para acessar esta página.'

# --- Imports for Routes and Models ---
from flask import render_template, url_for, flash, redirect, request, abort, session, g
from flask_login import login_user, current_user, logout_user, login_required
from flask import send_file, Response, jsonify, make_response
from werkzeug.utils import secure_filename
import io
import hmac
import hashlib
import secrets
import uuid
from functools import wraps
from urllib.parse import urlsplit
from openpyxl import Workbook, load_workbook
import re
import smtplib
import unicodedata
import zipfile
from email.message import EmailMessage
from sqlalchemy import func, cast, Date, text, or_, and_, false, exists
from datetime import datetime, timedelta
from forms import LoginForm, TenantLoginForm, RegistrationForm, ProtocoloForm, AnexoForm, AdminUserCreationForm, PlatformAdminCreationForm, AdminListItemForm, ConsultaPublicaForm, BrandingForm
from models import (Organizacao, OrganizacaoSubdominioAlias, Usuario, Protocolo, HistoricoProtocolo, Movimentacao,
                    ConsultaPublicaTentativa, LoginTentativa, Anexo, Lotacao,
                    TipoRequerimento, Servidor, ChamadoSuporte, MensagemSuporte,
                    OrganizacaoCapacidadeEvento, EmissaoEletronica, db)
from models import SolicitacaoComplemento
from models import PortalSessao, PortalRecuperacao, PortalCadastro
from models import AuditoriaEvento
from datetime import timezone
from sqlalchemy import event, select
from sqlalchemy.orm import Session
import json
from werkzeug.middleware.proxy_fix import ProxyFix

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

_RESERVED_SUBDOMAINS = {'app', 'www', 'admin', 'api', 'mail', 'smtp', 'static',
                        'suporte', 'dev', 'development', 'visual-development'}
_TENANT_URL_ENDPOINTS = {
    'tenant_login': '/entrar',
    'portal_login': '/portaldoservidor',
    'portal_cadastro': '/portal/cadastre-se',
    'portal_confirmar_cadastro': '/portal/confirmar-cadastro',
}


def _tenant_base_domain():
    """Ativação explícita: não gerar links novos antes de configurar o DNS."""
    if os.getenv('TENANT_SUBDOMAINS_ENABLED', '').lower() != 'true':
        return ''
    return os.getenv('TENANT_BASE_DOMAIN', '').strip().lower().strip('.')


def _tenant_host_label():
    base = _tenant_base_domain()
    hostname = request.host.partition(':')[0].lower().rstrip('.')
    if not base or not hostname.endswith('.' + base):
        return None
    label = hostname[:-(len(base) + 1)]
    if label in _RESERVED_SUBDOMAINS:
        return None
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label):
        abort(404)
    return label


def host_organization():
    if not hasattr(g, 'host_organization'):
        label = _tenant_host_label()
        if label:
            alias = OrganizacaoSubdominioAlias.query.filter_by(subdominio=label).first()
            g.host_organization = (Organizacao.query.filter_by(subdominio=label, ativo=True).first()
                                   or Organizacao.query.filter_by(slug=label, ativo=True).first()
                                   or (alias.organizacao if alias and alias.organizacao.ativo else None))
        else:
            g.host_organization = None
        if label and not g.host_organization:
            abort(404)
    return g.host_organization


def tenant_entry_url(endpoint, organization, *, token=None, external=False):
    """Retorna o endereço curto do cliente, preservando URLs legadas quando desativado."""
    base = _tenant_base_domain()
    if base:
        label = organization.subdominio or organization.slug
        path = (_TENANT_URL_ENDPOINTS.get(endpoint) or
                ('/portal/recuperar/' + token if endpoint == 'portal_recuperar' and token else None))
        if path:
            current = host_organization()
            if current and current.id == organization.id and not external:
                return path
            return f'https://{label}.{base}{path}'
    kwargs = {'slug': organization.slug, '_external': external}
    if token:
        kwargs['token'] = token
    return url_for(endpoint, **kwargs)


def public_url(endpoint, **values):
    """QR e recursos de PDF usam o domínio central, não o Host da requisição."""
    base = _tenant_base_domain()
    if base:
        return f'https://app.{base}' + url_for(endpoint, **values)
    return url_for(endpoint, _external=True, **values)


@app.before_request
def enforce_tenant_host():
    organization = host_organization()
    if not organization:
        return None
    slug = (request.view_args or {}).get('slug')
    if slug and slug != organization.slug:
        abort(404)
    if current_user.is_authenticated and (
            current_user.is_platform_admin or current_user.tenant_id != organization.id):
        abort(403)
    if not current_user.is_authenticated and request.endpoint == 'home' and request.path == '/':
        return redirect(url_for('tenant_login_host'))
    if request.endpoint == 'login':
        return redirect(url_for('tenant_login_host'))
    return None


@login_manager.unauthorized_handler
def unauthorized():
    organization = host_organization()
    if organization:
        if request.path.startswith('/portal'):
            return redirect(tenant_entry_url('portal_login', organization))
        return redirect(tenant_entry_url('tenant_login', organization))
    return redirect(url_for('login'))


@app.get('/acesso')
def tenant_access_legacy():
    if not host_organization():
        abort(404)
    return redirect(url_for('tenant_login_host'))


@app.route('/entrar', methods=['GET', 'POST'])
def tenant_login_host():
    organization = host_organization()
    if not organization:
        abort(404)
    return tenant_login(organization.slug)


@app.route('/portal/entrar', methods=['GET', 'POST'])
@app.route('/portaldoservidor', methods=['GET', 'POST'])
def portal_login_host():
    organization = host_organization()
    if not organization:
        abort(404)
    return portal_login(organization.slug)


@app.route('/portal/cadastre-se', methods=['GET', 'POST'])
def portal_cadastro_host():
    organization = host_organization()
    if not organization:
        abort(404)
    return portal_cadastro(organization.slug)


@app.route('/portal/confirmar-cadastro', methods=['GET', 'POST'])
def portal_confirmar_cadastro_host():
    organization = host_organization()
    if not organization:
        abort(404)
    return portal_confirmar_cadastro(organization.slug)


@app.route('/portal/recuperar/<string:token>', methods=['GET', 'POST'])
def portal_recuperar_host(token):
    organization = host_organization()
    if not organization:
        abort(404)
    return portal_recuperar(organization.slug, token)


@app.context_processor
def tenant_template_urls():
    return {'tenant_entry_url': tenant_entry_url, 'tenant_base_domain': _tenant_base_domain()}

def current_tenant_id():
    if current_user.is_authenticated and current_user.is_platform_admin:
        return session.get('active_tenant_id') or current_user.tenant_id
    return current_user.tenant_id

def active_organization():
    return db.session.get(Organizacao, current_tenant_id())

def tenant_query(model):
    """Consulta obrigatoriamente limitada à organização autenticada."""
    return model.query.filter(model.tenant_id == current_tenant_id())

def tenant_get_or_404(model, object_id):
    return tenant_query(model).filter(model.id == object_id).first_or_404()

def accessible_protocols_query():
    """Limita o tramitador aos processos dos quais seu setor ou ele participa."""
    query = tenant_query(Protocolo)
    if current_user.tipo == 'requerente':
        if not current_user.servidor_id:
            return query.filter(false())
        return query.filter(Protocolo.requerente_servidor_id == current_user.servidor_id)
    if current_user.tipo != 'tramitador':
        return query
    if not current_user.lotacao_id:
        return query.filter(false())
    participacao = exists().where(
        Movimentacao.tenant_id == current_tenant_id(),
        Movimentacao.protocolo_id == Protocolo.id,
        or_(Movimentacao.setor_origem_id == current_user.lotacao_id,
            and_(Movimentacao.setor_destino_id == current_user.lotacao_id,
                 or_(Movimentacao.destinatario_usuario_id.is_(None),
                     Movimentacao.destinatario_usuario_id == current_user.id)),
            Movimentacao.enviado_por_id == current_user.id,
            Movimentacao.recebido_por_id == current_user.id,
            Movimentacao.destinatario_usuario_id == current_user.id),
    )
    ultima_movimentacao = select(func.max(Movimentacao.id)).where(
        Movimentacao.tenant_id == current_tenant_id(),
        Movimentacao.protocolo_id == Protocolo.id).correlate(Protocolo).scalar_subquery()
    destino_nominal_alheio = exists().where(
        Movimentacao.id == ultima_movimentacao,
        Movimentacao.setor_destino_id == current_user.lotacao_id,
        Movimentacao.destinatario_usuario_id.is_not(None),
        Movimentacao.destinatario_usuario_id != current_user.id)
    return query.filter(or_(and_(Protocolo.setor_atual_id == current_user.lotacao_id,
                                ~destino_nominal_alheio), participacao))

def accessible_protocol_or_404(protocolo_id):
    return accessible_protocols_query().filter(Protocolo.id == protocolo_id).first_or_404()

def can_operate_protocol(protocolo):
    """Tramitadores só alteram processos que ainda estão sob custódia do seu setor."""
    if current_user.tipo != 'tramitador':
        return True
    return bool(current_user.lotacao_id and protocolo.setor_atual_id == current_user.lotacao_id)

def protocol_location(protocolo):
    """Descreve a localização operacional sem antecipar a transferência de custódia."""
    pendente = next((movimento for movimento in reversed(protocolo.movimentacoes)
                     if movimento.recebido_em is None), None)
    if pendente:
        origem = pendente.setor_origem.nome if pendente.setor_origem else 'setor de origem não definido'
        destino = pendente.setor_destino.nome if pendente.setor_destino else 'setor de destino não definido'
        destinatario = (f', aos cuidados de {pendente.destinatario_usuario.nome}'
                        if pendente.destinatario_usuario else '')
        return f'Em trânsito de {origem} para {destino}{destinatario} (aguardando recebimento)'
    return protocolo.setor_atual.nome if protocolo.setor_atual else 'Não definido'

def pendencias_recebimento_query():
    query = tenant_query(Movimentacao).filter(Movimentacao.recebido_em.is_(None))
    if current_user.tipo == 'admin':
        return query
    if not current_user.lotacao_id:
        return query.filter(false())
    return query.filter(
        Movimentacao.setor_destino_id == current_user.lotacao_id,
        or_(Movimentacao.destinatario_usuario_id.is_(None),
            Movimentacao.destinatario_usuario_id == current_user.id),
    )

def parse_iso_date(value, field_name):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        abort(400, description=f'{field_name} inválida.')

def apply_protocol_filters(query, args):
    """Mantém listagem, relatório e exportação com o mesmo resultado."""
    numero = (args.get('numero') or '').strip()
    nome = (args.get('nome') or '').strip()
    status = (args.get('status') or '').strip()
    data_inicio = parse_iso_date(args.get('data_inicio'), 'Data inicial')
    data_fim = parse_iso_date(args.get('data_fim'), 'Data final')
    tipo = (args.get('tipo') or '').strip()
    prazo = (args.get('prazo') or '').strip()
    if data_inicio and data_fim and data_inicio > data_fim:
        abort(400, description='A data inicial não pode ser posterior à data final.')
    if numero:
        query = query.filter(Protocolo.numero.ilike(f'%{numero}%'))
    if nome:
        query = query.filter(Protocolo.nome.ilike(f'%{nome}%'))
    if status:
        query = query.filter(Protocolo.status == status)
    if data_inicio:
        query = query.filter(Protocolo.data_solicitacao >= data_inicio)
    if data_fim:
        query = query.filter(Protocolo.data_solicitacao <= data_fim)
    if tipo:
        query = query.filter(Protocolo.tipo_requerimento.ilike(f'%{tipo}%'))
    hoje = datetime.now().date()
    ativos = ~Protocolo.status.in_(['FINALIZADO', 'CONCLUÍDO', 'ARQUIVADO'])
    if prazo == 'vencido':
        query = query.filter(Protocolo.prazo_em < hoje, ativos)
    elif prazo == 'hoje':
        query = query.filter(Protocolo.prazo_em == hoje, ativos)
    elif prazo == 'proximos_7':
        query = query.filter(Protocolo.prazo_em > hoje,
                             Protocolo.prazo_em <= hoje + timedelta(days=7), ativos)
    elif prazo == 'sem_prazo':
        query = query.filter(Protocolo.prazo_em.is_(None), ativos)
    elif prazo:
        abort(400, description='Situação de prazo inválida.')
    return query

def pagination_filter_args(args):
    return {key: value for key, value in args.items() if key != 'page' and value}

def safe_local_redirect(target):
    if not target:
        return None
    parsed = urlsplit(target)
    return target if not parsed.scheme and not parsed.netloc and target.startswith('/') else None

def verified_upload_mime(filename, data):
    extension = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if extension == 'pdf' and data.startswith(b'%PDF-'):
        return 'application/pdf'
    if extension in ('docx', 'xlsx') and data.startswith(b'PK\x03\x04'):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = set(archive.namelist())
                main_part = 'word/document.xml' if extension == 'docx' else 'xl/workbook.xml'
                if not {'[Content_Types].xml', '_rels/.rels', main_part}.issubset(names):
                    return None
                if (any(info.flag_bits & 1 for info in archive.infolist()) or
                        sum(info.file_size for info in archive.infolist()) > 50 * 1024 * 1024 or
                        any(name.lower().endswith('vbaproject.bin') for name in names)):
                    return None
                if archive.testzip() is not None:
                    return None
        except (zipfile.BadZipFile, RuntimeError, OSError):
            return None
        return {'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}[extension]
    if extension in ('doc', 'xls') and data.startswith(bytes.fromhex('D0CF11E0A1B11AE1')):
        return 'application/msword' if extension == 'doc' else 'application/vnd.ms-excel'
    if extension in ('png', 'jpg', 'jpeg', 'gif'):
        signatures = {'png': b'\x89PNG\r\n\x1a\n', 'jpg': b'\xff\xd8\xff', 'jpeg': b'\xff\xd8\xff', 'gif': b'GIF8'}
        if data.startswith(signatures[extension]):
            return 'image/png' if extension == 'png' else ('image/gif' if extension == 'gif' else 'image/jpeg')
    if extension in ('txt', 'csv'):
        try:
            data.decode('utf-8')
            return 'text/csv' if extension == 'csv' else 'text/plain'
        except UnicodeDecodeError:
            pass
    return None

def validated_uploads(files):
    """Lê e valida uma coleção de uploads sem persistir parcialmente o pedido."""
    validated = []
    total_size = 0
    for uploaded in files:
        if not uploaded or not uploaded.filename:
            continue
        filename = secure_filename(uploaded.filename)
        data = uploaded.read(5 * 1024 * 1024 + 1)
        if not filename or not data or len(data) > 5 * 1024 * 1024:
            raise ValueError('Cada anexo deve ter nome válido, conteúdo e no máximo 5 MB.')
        total_size += len(data)
        if total_size > 30 * 1024 * 1024:
            raise ValueError('O conjunto de anexos não pode ultrapassar 30 MB por envio.')
        mime_type = verified_upload_mime(filename, data)
        if not mime_type:
            raise ValueError(f'O arquivo {filename} possui formato ou conteúdo não permitido.')
        validated.append((filename, data, mime_type))
    return validated

def normalize_logo_png(source):
    """Valida, redimensiona e remove margens transparentes/brancas da logo."""
    from PIL import Image, ImageChops, ImageOps

    Image.MAX_IMAGE_PIXELS = 20_000_000
    image = Image.open(source)
    image.verify()
    source.seek(0)
    image = ImageOps.exif_transpose(Image.open(source)).convert('RGBA')

    alpha_box = image.getchannel('A').getbbox()
    if alpha_box and alpha_box != (0, 0, image.width, image.height):
        content_box = alpha_box
    else:
        rgb = image.convert('RGB')
        white = Image.new('RGB', rgb.size, 'white')
        difference = ImageChops.difference(rgb, white).convert('L').point(
            lambda value: 255 if value > 12 else 0
        )
        content_box = difference.getbbox()
    if content_box:
        padding = max(4, round(max(image.size) * 0.01))
        left, top, right, bottom = content_box
        image = image.crop((max(0, left - padding), max(0, top - padding),
                            min(image.width, right + padding), min(image.height, bottom + padding)))

    image.thumbnail((1600, 800))
    output = io.BytesIO()
    image.save(output, format='PNG', optimize=True)
    output.seek(0)
    return output

def bucket_configured():
    return all(os.getenv(name) for name in (
        'AWS_ENDPOINT_URL', 'AWS_S3_BUCKET_NAME', 'AWS_DEFAULT_REGION',
        'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY'))

def bucket_client():
    if not bucket_configured():
        return None
    import boto3
    from botocore.config import Config
    return boto3.client(
        's3', endpoint_url=os.environ['AWS_ENDPOINT_URL'],
        region_name=os.environ['AWS_DEFAULT_REGION'],
        aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
        config=Config(s3={'addressing_style': os.getenv('AWS_S3_URL_STYLE', 'virtual')}),
    )

def store_attachment_bytes(data, tenant_id, protocolo_id, documento_chave, versao, filename, mime_type):
    digest = hashlib.sha256(data).hexdigest()
    client = bucket_client()
    if not client:
        return f'{protocolo_id}/{filename}', 'database', digest, data
    extension = os.path.splitext(filename)[1].lower()
    key = (f'tenants/{tenant_id}/protocolos/{protocolo_id}/documentos/'
           f'{documento_chave}/v{versao}/{uuid.uuid4().hex}{extension}')
    client.put_object(Bucket=os.environ['AWS_S3_BUCKET_NAME'], Key=key, Body=data,
                      ContentType=mime_type, Metadata={'sha256': digest})
    return key, 's3', digest, None

def read_attachment_bytes(anexo):
    if anexo.storage_backend == 's3':
        client = bucket_client()
        if not client:
            raise RuntimeError('Armazenamento de anexos indisponível.')
        response = client.get_object(Bucket=os.environ['AWS_S3_BUCKET_NAME'], Key=anexo.storage_path)
        data = response['Body'].read()
    else:
        data = anexo.file_data
    if data is None or (anexo.file_hash and not hmac.compare_digest(hashlib.sha256(data).hexdigest(), anexo.file_hash)):
        raise RuntimeError('O anexo não pôde ser validado.')
    return data

ROLE_PERMISSIONS = {
    'admin': {'view', 'create', 'edit', 'route', 'archive', 'delete', 'manage', 'reports'},
    # Cria e mantém protocolos, mas não administra usuários, setores ou a identidade do cliente.
    'protocolista': {'view', 'create', 'edit', 'route', 'reports'},
    # Atua somente no fluxo: recebe, encaminha e responde processos do seu setor/usuário.
    'tramitador': {'view', 'route'},
    'consulta': {'view'},
    # Acesso exclusivo ao Portal do Servidor; não concede acesso ao backoffice.
    'requerente': set(),
}
ROLE_LABELS = {
    'admin': 'Administrador do cliente',
    'protocolista': 'Protocolista',
    'tramitador': 'Tramitação e respostas',
    'consulta': 'Somente consulta',
    'requerente': 'Servidor — Portal do Servidor',
}
PROTOCOL_STATUSES = ('PROTOCOLO GERADO', 'EM ANÁLISE', 'PENDENTE DE DOCUMENTO', 'FINALIZADO', 'CONCLUÍDO', 'EM TRAMITAÇÃO', 'ARQUIVADO')
SUPPORT_STATUSES = ('ABERTO', 'EM ATENDIMENTO', 'AGUARDANDO USUÁRIO', 'RESOLVIDO', 'FECHADO')
SUPPORT_CATEGORIES = ('ACESSO', 'PROTOCOLOS', 'DOCUMENTOS', 'RELATÓRIOS', 'CONFIGURAÇÃO', 'OUTRO')
SUPPORT_PRIORITIES = ('BAIXA', 'NORMAL', 'ALTA', 'CRÍTICA')
HISTORY_ACTION_LABELS = {
    'ENVIO_REMOTO': 'Requerimento enviado pelo portal',
    'COMPLEMENTO_SOLICITADO': 'Documentação complementar solicitada',
    'COMPLEMENTO_ENVIADO': 'Documentação complementar enviada',
    'EMISSAO_AUTENTICADA': 'Requerimento autenticado',
    'EMISSAO_CANCELADA': 'Autenticação cancelada',
    'RETIFICACAO': 'Retificação registrada',
    'TRAMITACAO': 'Encaminhamento',
    'RECEBIMENTO': 'Recebimento',
    'ARQUIVAMENTO': 'Arquivamento',
    'ALTERACAO_STATUS': 'Alteração de situação',
    'ANEXO_ADICIONADO': 'Documento anexado',
    'NOVA_VERSAO_DOCUMENTO': 'Nova versão de documento',
}
EMISSION_STATUS_LABELS = {'VALIDA': 'Válida', 'RETIFICADA': 'Retificada', 'CANCELADA': 'Cancelada'}

def history_observation_label(observation):
    if observation == 'Requerimento enviado pelo próprio servidor em conta individual vinculada ao cadastro funcional.':
        return 'Pedido enviado pelo próprio servidor por meio do Portal do Servidor.'
    return observation or 'Sem observação.'

def support_tickets_query():
    query = ChamadoSuporte.query
    if current_user.is_platform_admin:
        return query
    return query.filter(ChamadoSuporte.tenant_id == current_user.tenant_id,
                        ChamadoSuporte.aberto_por_id == current_user.id)

def accessible_support_ticket_or_404(ticket_id):
    return support_tickets_query().filter(ChamadoSuporte.id == ticket_id).first_or_404()

@app.context_processor
def permission_context():
    logo_url = url_for('static', filename='img/logo-sysprot.svg')
    organization = active_organization() if current_user.is_authenticated else None
    if organization:
        version = int(organization.logo_atualizada_em.timestamp()) if organization.logo_atualizada_em else 0
        logo_url = url_for('organization_logo', slug=organization.slug, v=version)
    pendencias_recebimento = 0
    if current_user.is_authenticated:
        pendencias_recebimento = pendencias_recebimento_query().count()
    chamados_pendentes = 0
    if current_user.is_authenticated:
        chamados_pendentes = support_tickets_query().filter(
            ~ChamadoSuporte.status.in_(['RESOLVIDO', 'FECHADO'])).count()
    return {
        'can': lambda permission: current_user.is_authenticated and permission in ROLE_PERMISSIONS.get(current_user.tipo, set()),
        'protocol_location': protocol_location,
        'role_labels': ROLE_LABELS,
        'active_organization': organization,
        'branding_logo_url': logo_url,
        'pendencias_recebimento': pendencias_recebimento,
        'chamados_pendentes': chamados_pendentes,
        'history_action_label': lambda action: HISTORY_ACTION_LABELS.get(
            action, (action or 'Atualização').replace('_', ' ').title()),
        'emission_status_label': lambda status: EMISSION_STATUS_LABELS.get(status, status.title()),
        'history_observation_label': history_observation_label,
    }

def permission_required(permission):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if permission not in ROLE_PERMISSIONS.get(current_user.tipo, set()):
                if request.is_json:
                    return jsonify({'erro': 'Acesso negado.'}), 403
                flash('Acesso negado.', 'danger')
                return redirect(url_for('home'))
            return view(*args, **kwargs)
        return wrapped
    return decorator

# --- Routes ---
@app.get('/health')
def health():
    """Prontidão real: o processo e sua dependência essencial devem responder."""
    try:
        db.session.execute(text('SELECT 1'))
    except Exception:
        db.session.rollback()
        return jsonify({'status': 'indisponivel', 'database': 'erro'}), 503
    return jsonify({'status': 'ok', 'database': 'ok'})

@app.get('/identidade/<string:slug>/logo')
def organization_logo(slug):
    organizacao = Organizacao.query.filter_by(slug=slug.strip().lower(), ativo=True).first()
    if not organizacao or not organizacao.logo_data:
        default_slug = os.getenv('DEFAULT_ORGANIZATION_SLUG', 'prefeitura').strip().lower()
        fallback = 'img/logo.png' if organizacao and organizacao.slug == default_slug else 'img/logo-sysprot.svg'
        return redirect(url_for('static', filename=fallback))
    try:
        logo_stream = normalize_logo_png(io.BytesIO(organizacao.logo_data))
    except Exception:
        app.logger.exception('Falha ao normalizar a logo da organização %s.', organizacao.id)
        logo_stream = io.BytesIO(organizacao.logo_data)
    response = send_file(logo_stream, mimetype='image/png',
                         download_name='logo.png', max_age=3600, conditional=True)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    # Flask-WTF valida o Referer em POSTs HTTPS. "same-origin" mantém esse
    # cabeçalho apenas dentro do Sysprot e não revela a URL a sites externos.
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net "
        "https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: blob:; connect-src 'self' https://viacep.com.br; font-src 'self' data:; "
        "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; "
        "worker-src 'self' blob:"
    )
    if request.is_secure:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    if current_user.is_authenticated or request.endpoint in ('login', 'consulta_publica'):
        response.headers['Cache-Control'] = 'no-store, max-age=0'
        response.headers['Pragma'] = 'no-cache'
    if request.path.startswith('/consulta/'):
        response.headers['Cache-Control'] = 'no-store, max-age=0'
        response.headers['Content-Security-Policy'] = (
            "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
            "frame-ancestors 'none'; base-uri 'none'"
        )
    return response

def consulta_fingerprint():
    endereco = request.remote_addr or 'desconhecido'
    return hmac.new(app.config['SECRET_KEY'].encode(), endereco.encode(), hashlib.sha256).hexdigest()


def login_fingerprint(organizacao, login):
    origem = request.remote_addr or ''
    valor = f'{organizacao.strip().lower()}\0{login.strip().lower()}\0{origem}'
    return hmac.new(app.config['SECRET_KEY'].encode(), valor.encode(), hashlib.sha256).hexdigest()

@app.route('/consulta/<string:consulta_token>', methods=['GET', 'POST'])
def consulta_publica(consulta_token):
    """Exige confirmação da matrícula antes de exibir o andamento."""
    protocolo = Protocolo.query.filter_by(consulta_token=consulta_token).first_or_404()
    organizacao = Organizacao.query.filter_by(id=protocolo.tenant_id, ativo=True).first_or_404()
    form = ConsultaPublicaForm()
    consulta_autorizada = False
    erro_consulta = None
    historico = []
    if form.validate_on_submit():
        agora = datetime.utcnow()
        fingerprint = consulta_fingerprint()
        tentativa = ConsultaPublicaTentativa.query.filter_by(
            protocolo_id=protocolo.id, identificador_hash=fingerprint
        ).first()
        if tentativa and tentativa.bloqueado_ate and tentativa.bloqueado_ate > agora:
            erro_consulta = 'Limite de tentativas atingido. Tente novamente mais tarde.'
            resposta = render_template('consulta_publica.html', protocolo=protocolo,
                                        organizacao=organizacao, historico=[], form=form,
                                        consulta_autorizada=False, erro_consulta=erro_consulta)
            return resposta, 429
        matricula_armazenada = (protocolo.matricula or '').strip().casefold()
        matricula_informada = form.matricula.data.strip().casefold()
        consulta_autorizada = bool(matricula_armazenada) and hmac.compare_digest(
            matricula_armazenada.encode('utf-8'), matricula_informada.encode('utf-8')
        )
        if consulta_autorizada:
            if tentativa:
                db.session.delete(tentativa)
            historico = HistoricoProtocolo.query.filter_by(
                tenant_id=organizacao.id, protocolo_id=protocolo.id
            ).order_by(HistoricoProtocolo.data_movimentacao.desc()).all()
            db.session.commit()
        else:
            janela = timedelta(minutes=15)
            if not tentativa:
                tentativa = ConsultaPublicaTentativa(
                    protocolo_id=protocolo.id, identificador_hash=fingerprint,
                    tentativas=0, janela_iniciada_em=agora
                )
                db.session.add(tentativa)
            elif tentativa.janela_iniciada_em < agora - janela:
                tentativa.tentativas = 0
                tentativa.janela_iniciada_em = agora
                tentativa.bloqueado_ate = None
            tentativa.tentativas += 1
            if tentativa.tentativas >= 5:
                tentativa.bloqueado_ate = agora + timedelta(minutes=30)
            db.session.commit()
            erro_consulta = 'Não foi possível validar os dados informados.'
    elif request.method == 'POST':
        erro_consulta = 'Não foi possível validar os dados informados.'
    return render_template('consulta_publica.html', protocolo=protocolo,
                           organizacao=organizacao, historico=historico,
                           form=form, consulta_autorizada=consulta_autorizada,
                           erro_consulta=erro_consulta)

@app.route("/")
@app.route("/home")
@login_required
def home():
    # This page will now be rendered with the dashboard structure,
    # and the data will be fetched client-side.
    return render_template('home.html', title="Dashboard")


@app.get('/suporte')
@login_required
def support_list():
    status = (request.args.get('status') or '').strip().upper()
    query = support_tickets_query()
    if status:
        if status not in SUPPORT_STATUSES:
            abort(400, description='Status de chamado inválido.')
        query = query.filter(ChamadoSuporte.status == status)
    chamados = query.order_by(ChamadoSuporte.atualizado_em.desc(),
                              ChamadoSuporte.id.desc()).all()
    return render_template('suporte.html', title='Suporte', chamados=chamados,
                           support_statuses=SUPPORT_STATUSES)


@app.post('/suporte/novo')
@login_required
def support_create():
    assunto = (request.form.get('assunto') or '').strip()
    descricao = (request.form.get('descricao') or '').strip()
    categoria = (request.form.get('categoria') or '').strip().upper()
    prioridade = (request.form.get('prioridade') or '').strip().upper()
    if not 5 <= len(assunto) <= 180 or not 10 <= len(descricao) <= 5000:
        flash('Informe um assunto e uma descrição suficientemente detalhada.', 'danger')
        return redirect(url_for('support_list'))
    if categoria not in SUPPORT_CATEGORIES or prioridade not in SUPPORT_PRIORITIES:
        abort(400, description='Classificação de chamado inválida.')
    # O administrador geral também possui uma organização de origem. Chamados
    # abertos por ele permanecem vinculados a essa organização, ainda que esteja
    # administrando outro cliente no momento.
    tenant_id = current_user.tenant_id if current_user.is_platform_admin else current_tenant_id()
    chamado = ChamadoSuporte(
        tenant_id=tenant_id, assunto=assunto, descricao=descricao,
        categoria=categoria, prioridade=prioridade, status='ABERTO',
        aberto_por_id=current_user.id)
    db.session.add(chamado)
    db.session.commit()
    flash(f'Chamado SUP-{chamado.id:06d} aberto com sucesso.', 'success')
    return redirect(url_for('support_detail', ticket_id=chamado.id))


@app.get('/suporte/<int:ticket_id>')
@login_required
def support_detail(ticket_id):
    chamado = accessible_support_ticket_or_404(ticket_id)
    organizacao_chamado = db.session.get(Organizacao, chamado.tenant_id)
    return render_template('suporte_detalhe.html', title=f'Chamado SUP-{chamado.id:06d}',
                           chamado=chamado, organizacao_chamado=organizacao_chamado,
                           support_statuses=SUPPORT_STATUSES)


@app.post('/suporte/<int:ticket_id>/mensagem')
@login_required
def support_reply(ticket_id):
    chamado = accessible_support_ticket_or_404(ticket_id)
    if chamado.status == 'FECHADO':
        flash('Chamados fechados não aceitam novas mensagens.', 'warning')
        return redirect(url_for('support_detail', ticket_id=chamado.id))
    mensagem = (request.form.get('mensagem') or '').strip()
    if not 2 <= len(mensagem) <= 5000:
        flash('A mensagem deve conter entre 2 e 5.000 caracteres.', 'danger')
        return redirect(url_for('support_detail', ticket_id=chamado.id))
    db.session.add(MensagemSuporte(
        tenant_id=chamado.tenant_id, chamado_id=chamado.id,
        autor_id=current_user.id, mensagem=mensagem))
    chamado.atualizado_em = datetime.utcnow()
    if not current_user.is_platform_admin and chamado.status == 'AGUARDANDO USUÁRIO':
        chamado.status = 'EM ATENDIMENTO'
    db.session.commit()
    flash('Mensagem adicionada ao chamado.', 'success')
    return redirect(url_for('support_detail', ticket_id=chamado.id))


@app.post('/suporte/<int:ticket_id>/assumir')
@login_required
def support_assign(ticket_id):
    if not current_user.is_platform_admin:
        abort(403)
    chamado = ChamadoSuporte.query.filter_by(id=ticket_id).first_or_404()
    if chamado.status in ('RESOLVIDO', 'FECHADO'):
        flash('O chamado já está encerrado.', 'warning')
        return redirect(url_for('support_detail', ticket_id=chamado.id))
    chamado.atribuido_a_id = current_user.id
    chamado.status = 'EM ATENDIMENTO'
    chamado.atualizado_em = datetime.utcnow()
    db.session.commit()
    flash(f'Chamado SUP-{chamado.id:06d} atribuído a você.', 'success')
    return redirect(url_for('support_detail', ticket_id=chamado.id))


@app.post('/suporte/<int:ticket_id>/status')
@login_required
def support_update_status(ticket_id):
    if not current_user.is_platform_admin:
        abort(403)
    chamado = ChamadoSuporte.query.filter_by(id=ticket_id).first_or_404()
    novo_status = (request.form.get('status') or '').strip().upper()
    if novo_status not in SUPPORT_STATUSES:
        abort(400, description='Status de chamado inválido.')
    if not chamado.atribuido_a_id:
        chamado.atribuido_a_id = current_user.id
    chamado.status = novo_status
    chamado.atualizado_em = datetime.utcnow()
    chamado.encerrado_em = datetime.utcnow() if novo_status in ('RESOLVIDO', 'FECHADO') else None
    db.session.commit()
    flash('Status do chamado atualizado.', 'success')
    return redirect(url_for('support_detail', ticket_id=chamado.id))

@app.get('/pendencias-recebimento')
@permission_required('route')
def pendencias_recebimento():
    movimentos = pendencias_recebimento_query().order_by(Movimentacao.enviado_em.desc()).all()
    return render_template('pendencias_recebimento.html', title='Pendências de recebimento', movimentos=movimentos)

@app.route("/register", methods=['GET', 'POST'])
def register():
    flash('O cadastro público está desativado. Solicite acesso ao administrador da organização.', 'info')
    return redirect(url_for('login'))


@app.route('/entrar/<string:slug>', methods=['GET', 'POST'])
def tenant_login(slug):
    """Entrada do backoffice com a organização resolvida antes da autenticação."""
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    organizacao = Organizacao.query.filter_by(slug=slug.strip().lower(), ativo=True).first_or_404()
    form = TenantLoginForm()
    if form.validate_on_submit():
        agora = datetime.utcnow()
        fingerprint = login_fingerprint(organizacao.slug, form.login.data)
        tentativa = LoginTentativa.query.filter_by(identificador_hash=fingerprint).with_for_update().first()
        if tentativa and tentativa.bloqueado_ate and tentativa.bloqueado_ate > agora:
            flash('Não foi possível autenticar. Aguarde alguns minutos e tente novamente.', 'danger')
            return render_template(
                'login.html', title=f'Login — {organizacao.nome}', form=form,
                login_organization=organizacao,
                branding_logo_url=url_for('organization_logo', slug=organizacao.slug),
            ), 429
        if tentativa and tentativa.janela_iniciada_em < agora - timedelta(minutes=15):
            tentativa.tentativas = 0
            tentativa.janela_iniciada_em = agora
            tentativa.bloqueado_ate = None
        user = Usuario.query.filter_by(
            tenant_id=organizacao.id, login=form.login.data, status='ativo'
        ).first()
        if (user and user.tipo != 'requerente'
                and not (user.is_platform_admin and host_organization())
                and bcrypt.check_password_hash(user.senha, form.senha.data)):
            if tentativa:
                db.session.delete(tentativa)
                db.session.commit()
            login_user(user, remember=form.remember.data)
            session['auth_surface'] = 'backoffice'
            destination = safe_local_redirect(request.args.get('next'))
            if user.is_platform_admin:
                session.pop('active_tenant_id', None)
                destination = url_for('platform_organizations')
            flash('Login bem-sucedido!', 'success')
            return redirect(destination or url_for('home'))
        if not tentativa:
            tentativa = LoginTentativa(
                identificador_hash=fingerprint, tentativas=0, janela_iniciada_em=agora
            )
            db.session.add(tentativa)
        tentativa.tentativas += 1
        if tentativa.tentativas >= 5:
            tentativa.bloqueado_ate = agora + timedelta(minutes=30)
        db.session.commit()
        flash('Não foi possível autenticar. Verifique os dados informados.', 'danger')
    return render_template(
        'login.html', title=f'Login — {organizacao.nome}', form=form,
        login_organization=organizacao,
        branding_logo_url=url_for('organization_logo', slug=organizacao.slug),
    )


def portal_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        organizacao = active_organization()
        if (current_user.tipo != 'requerente' or not current_user.servidor_id or
                not organizacao.portal_servidor_remoto_enabled or session.get('auth_surface') != 'portal'):
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def _portal_token_hash(token):
    return hmac.new(app.config['SECRET_KEY'].encode(), token.encode(), hashlib.sha256).hexdigest()


def _portal_now():
    return datetime.now(timezone.utc)


def _audit_digest(previous, payload):
    return hashlib.sha256((previous + '\n' + payload).encode('utf-8')).hexdigest()


@event.listens_for(Session, 'before_flush')
def append_protocol_audit(db_session, flush_context, instances):
    """Encadeia os novos eventos de protocolo sob bloqueio da organização."""
    pending = [item for item in db_session.new if isinstance(item, HistoricoProtocolo)]
    for tenant_id in sorted({item.tenant_id for item in pending}):
        db_session.execute(select(Organizacao.id).where(
            Organizacao.id == tenant_id).with_for_update()).first()
        last = db_session.query(AuditoriaEvento).filter_by(tenant_id=tenant_id).order_by(
            AuditoriaEvento.sequencia.desc()).first()
        previous = last.hash_atual if last else '0' * 64
        sequence = last.sequencia if last else 0
        for item in (entry for entry in pending if entry.tenant_id == tenant_id):
            sequence += 1
            item.evento_uuid = str(uuid.uuid4())
            if item.data_movimentacao is None:
                item.data_movimentacao = datetime.now(timezone.utc).replace(tzinfo=None)
            payload = json.dumps({
                'versao': 2, 'tenant_id': tenant_id, 'sequencia': sequence,
                'data_movimentacao': item.data_movimentacao.isoformat(timespec='microseconds'),
                'evento_uuid': item.evento_uuid,
                'protocolo_id': item.protocolo_id, 'usuario_id': item.usuario_id,
                'acao': item.acao, 'status': item.status,
                'responsavel': item.responsavel, 'observacao': item.observacao,
            }, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
            current = _audit_digest(previous, payload)
            db_session.add(AuditoriaEvento(
                tenant_id=tenant_id, sequencia=sequence,
                protocolo_id=item.protocolo_id, usuario_id=item.usuario_id,
                acao=item.acao, payload=payload,
                hash_anterior=previous, hash_atual=current))
            previous = current


def verify_audit_chain(tenant_id):
    records = AuditoriaEvento.query.filter_by(tenant_id=tenant_id).order_by(
        AuditoriaEvento.sequencia).all()
    previous = '0' * 64
    uuids = [json.loads(item.payload).get('evento_uuid') for item in records]
    histories = {item.evento_uuid: item for item in HistoricoProtocolo.query.filter(
        HistoricoProtocolo.tenant_id == tenant_id,
        HistoricoProtocolo.evento_uuid.in_(uuids)).all()}
    for expected, item in enumerate(records, start=1):
        if (item.sequencia != expected or item.hash_anterior != previous or
                not hmac.compare_digest(item.hash_atual, _audit_digest(previous, item.payload))):
            return False, records, expected
        payload = json.loads(item.payload)
        history = histories.get(payload.get('evento_uuid'))
        if not history or any(payload.get(field) != getattr(history, field) for field in (
                'tenant_id', 'protocolo_id', 'usuario_id', 'acao', 'status',
                'responsavel', 'observacao')):
            return False, records, expected
        if payload.get('versao', 1) >= 2 and (
                not history.data_movimentacao or
                payload.get('data_movimentacao') != history.data_movimentacao.replace(
                    tzinfo=None).isoformat(timespec='microseconds')):
            return False, records, expected
        previous = item.hash_atual
    return True, records, None


def _portal_session():
    token = session.get('portal_session_token')
    if not token or not current_user.is_authenticated:
        return None
    return PortalSessao.query.filter_by(
        tenant_id=current_user.tenant_id, usuario_id=current_user.id,
        identificador_hash=_portal_token_hash(token), encerrada_em=None).first()


@app.before_request
def validate_portal_session():
    if not current_user.is_authenticated or current_user.tipo != 'requerente':
        return None
    record = _portal_session()
    now = _portal_now()
    expires = record.expira_em.replace(tzinfo=timezone.utc) if record and record.expira_em.tzinfo is None else (record.expira_em if record else None)
    if session.get('auth_surface') != 'portal' or not record or expires <= now:
        organization = current_user.organizacao
        session.pop('portal_session_token', None)
        session.pop('auth_surface', None)
        logout_user()
        return redirect(tenant_entry_url('portal_login', organization))
    last_access = record.ultimo_acesso_em.replace(tzinfo=timezone.utc) if record.ultimo_acesso_em.tzinfo is None else record.ultimo_acesso_em
    if request.endpoint != 'static' and now - last_access >= timedelta(minutes=5):
        record.ultimo_acesso_em = now
        db.session.commit()
    return None


@app.route('/portal/<string:slug>/entrar', methods=['GET', 'POST'])
def portal_login(slug):
    organizacao = Organizacao.query.filter_by(slug=slug.strip().lower(), ativo=True).first_or_404()
    if not organizacao.portal_servidor_remoto_enabled:
        abort(404)
    if current_user.is_authenticated:
        return redirect(url_for('portal_home') if current_user.tipo == 'requerente' else url_for('home'))
    form = TenantLoginForm()
    if form.validate_on_submit():
        agora = datetime.utcnow()
        fingerprint = login_fingerprint(f'portal:{organizacao.slug}', form.login.data)
        tentativa = LoginTentativa.query.filter_by(identificador_hash=fingerprint).with_for_update().first()
        if tentativa and tentativa.bloqueado_ate and tentativa.bloqueado_ate > agora:
            flash('Não foi possível autenticar. Aguarde alguns minutos e tente novamente.', 'danger')
            return render_template('portal_login.html', form=form, organizacao=organizacao), 429
        if tentativa and tentativa.janela_iniciada_em < agora - timedelta(minutes=15):
            tentativa.tentativas = 0
            tentativa.janela_iniciada_em = agora
            tentativa.bloqueado_ate = None
        user = Usuario.query.filter_by(tenant_id=organizacao.id, login=form.login.data,
                                       tipo='requerente', status='ativo').first()
        if user and user.servidor_id and bcrypt.check_password_hash(user.senha, form.senha.data):
            if tentativa:
                db.session.delete(tentativa)
                db.session.commit()
            login_user(user, remember=False)
            session['auth_surface'] = 'portal'
            token = secrets.token_urlsafe(32)
            session['portal_session_token'] = token
            db.session.add(PortalSessao(
                tenant_id=organizacao.id, usuario_id=user.id,
                identificador_hash=_portal_token_hash(token),
                dispositivo=(request.user_agent.string or 'Navegador não identificado')[:180],
                expira_em=_portal_now() + timedelta(hours=12)))
            db.session.commit()
            flash('Acesso realizado com segurança.', 'success')
            return redirect(url_for('portal_home'))
        if not tentativa:
            tentativa = LoginTentativa(identificador_hash=fingerprint, tentativas=0,
                                        janela_iniciada_em=agora)
            db.session.add(tentativa)
        tentativa.tentativas += 1
        if tentativa.tentativas >= 5:
            tentativa.bloqueado_ate = agora + timedelta(minutes=30)
        db.session.commit()
        flash('Não foi possível autenticar. Verifique os dados informados.', 'danger')
    return render_template('portal_login.html', form=form, organizacao=organizacao)


def _send_account_email(destination, subject, body):
    host = os.getenv('SMTP_HOST', '').strip()
    sender = os.getenv('SMTP_FROM', '').strip()
    if not host or not sender:
        raise RuntimeError('O envio de e-mail ainda não foi configurado.')
    message = EmailMessage()
    message['From'] = sender
    message['To'] = destination
    message['Subject'] = subject
    message.set_content(body)
    port = int(os.getenv('SMTP_PORT', '587'))
    with smtplib.SMTP(host, port, timeout=15) as server:
        server.starttls()
        username = os.getenv('SMTP_USER', '').strip()
        if username:
            server.login(username, os.getenv('SMTP_PASSWORD', ''))
        server.send_message(message)


def _identity_text(value):
    normalized = unicodedata.normalize('NFKD', (value or '').strip().casefold())
    return ' '.join(''.join(c for c in normalized if not unicodedata.combining(c)).split())


def _strong_password(value):
    return 12 <= len(value) <= 128 and value.strip() == value and value.casefold() not in {
        '123456789012', 'admin12345678', 'password123456', 'senha12345678'}


def _portal_password_valid(value):
    return (8 <= len(value) <= 128 and value.strip() == value
            and any(char.islower() for char in value)
            and any(char.isupper() for char in value)
            and any(char.isdigit() for char in value))


def _email_code_hash(record_id, code):
    return hmac.new(app.config['SECRET_KEY'].encode(), f'{record_id}:{code}'.encode(), hashlib.sha256).hexdigest()


def _as_aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _confirmar_pin_usuario(user, pin):
    now = _portal_now()
    if user.pin_bloqueado_ate and _as_aware(user.pin_bloqueado_ate) > now:
        return False
    if not user.pin_hash or not re.fullmatch(r'\d{6}', pin or '') or not bcrypt.check_password_hash(user.pin_hash, pin):
        user.pin_erros = (user.pin_erros or 0) + 1
        if user.pin_erros >= 5:
            user.pin_bloqueado_ate = now + timedelta(minutes=30)
            user.pin_erros = 0
        db.session.commit()
        return False
    user.pin_erros = 0
    user.pin_bloqueado_ate = None
    db.session.flush()
    return True


_SIGNUP_QUESTIONS = {
    'primeiro_nome_mae': 'Qual é o primeiro nome da sua mãe?',
    'ultimo_nome_mae': 'Qual é o último nome da sua mãe?',
    'ano_nascimento': 'Em que ano você nasceu?',
    'mes_nascimento': 'Em que mês você nasceu? Informe o número de 1 a 12.',
    'dia_nascimento': 'Em que dia do mês você nasceu?',
}


def _signup_challenge(organization):
    challenge = session.get('portal_identificacao')
    if (not isinstance(challenge, dict) or challenge.get('tenant_id') != organization.id
            or challenge.get('expira', 0) <= _portal_now().timestamp()):
        session.pop('portal_identificacao', None)
        return None
    return challenge


def _render_signup(organization):
    challenge = _signup_challenge(organization)
    if not challenge:
        return render_template('portal_identificar_cadastro.html', organizacao=organization)
    return render_template('portal_cadastro.html', organizacao=organization,
                           matricula=challenge['matricula'],
                           perguntas=[(field, _SIGNUP_QUESTIONS[field]) for field in challenge['perguntas']])


@app.route('/portal/<string:slug>/cadastre-se', methods=['GET', 'POST'])
def portal_cadastro(slug):
    organizacao = Organizacao.query.filter_by(slug=slug.strip().lower(), ativo=True,
                                               portal_servidor_remoto_enabled=True).first_or_404()
    if current_user.is_authenticated:
        return redirect(url_for('portal_home') if current_user.tipo == 'requerente' else url_for('home'))
    if request.method == 'POST':
        matricula = (request.form.get('matricula') or '').strip()[:80]
        nome = _identity_text(request.form.get('nome'))
        cpf = re.sub(r'\D', '', request.form.get('cpf') or '')
        email = (request.form.get('email') or '').strip().lower()
        telefone = (request.form.get('telefone') or '').strip()[:30]
        endereco = (request.form.get('endereco') or '').strip()[:500]
        senha = request.form.get('senha') or ''
        confirmar_senha = request.form.get('confirmar_senha') or ''
        fingerprint = login_fingerprint(f'cadastro:{organizacao.slug}', matricula)
        now = datetime.utcnow()
        tentativa = LoginTentativa.query.filter_by(identificador_hash=fingerprint).with_for_update().first()
        if tentativa and tentativa.bloqueado_ate and tentativa.bloqueado_ate > now:
            flash('Não foi possível concluir o cadastro agora. Tente novamente mais tarde.', 'danger')
            return _render_signup(organizacao), 429
        if tentativa and tentativa.janela_iniciada_em < now - timedelta(minutes=15):
            tentativa.tentativas = 0
            tentativa.janela_iniciada_em = now
            tentativa.bloqueado_ate = None
        servidor = Servidor.query.filter_by(tenant_id=organizacao.id, matricula=matricula).with_for_update().first()
        elegivel = bool(servidor and servidor.cpf and servidor.nascimento and servidor.nome_mae
                        and not Usuario.query.filter_by(tenant_id=organizacao.id,
                                                        servidor_id=servidor.id).first())
        if request.form.get('etapa') == 'identificar':
            if elegivel:
                session['portal_identificacao'] = {
                    'tenant_id': organizacao.id, 'matricula': matricula,
                    'expira': (_portal_now() + timedelta(minutes=15)).timestamp(),
                    'perguntas': [secrets.choice(['primeiro_nome_mae', 'ultimo_nome_mae']),
                                 secrets.choice(['ano_nascimento', 'mes_nascimento', 'dia_nascimento'])]}
                return redirect(tenant_entry_url('portal_cadastro', organizacao))
            if not tentativa:
                tentativa = LoginTentativa(identificador_hash=fingerprint, tentativas=0, janela_iniciada_em=now)
                db.session.add(tentativa)
            tentativa.tentativas += 1
            if tentativa.tentativas >= 5:
                tentativa.bloqueado_ate = now + timedelta(minutes=30)
            db.session.commit()
            flash('Não foi possível iniciar o cadastro com essa matrícula. Confira o número ou procure o setor responsável.', 'danger')
            return _render_signup(organizacao), 400
        challenge = _signup_challenge(organizacao)
        respostas = {}
        if elegivel:
            mae = _identity_text(servidor.nome_mae).split()
            respostas = {'primeiro_nome_mae': mae[0], 'ultimo_nome_mae': mae[-1],
                         'ano_nascimento': str(servidor.nascimento.year),
                         'mes_nascimento': str(servidor.nascimento.month),
                         'dia_nascimento': str(servidor.nascimento.day)}
        valid = bool(elegivel and challenge and challenge['matricula'] == matricula
                     and _identity_text(servidor.nome) == nome and servidor.cpf == cpf)
        if valid:
            for field in challenge['perguntas']:
                answer = _identity_text(request.form.get(field))
                if field.endswith('nascimento') and answer.isdigit():
                    answer = str(int(answer))
                if answer != respostas[field]:
                    valid = False
                    break
        if (not valid or not _portal_password_valid(senha) or senha != confirmar_senha
                or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email)
                or not telefone or not endereco):
            if not tentativa:
                tentativa = LoginTentativa(identificador_hash=fingerprint, tentativas=0, janela_iniciada_em=now)
                db.session.add(tentativa)
            tentativa.tentativas += 1
            if tentativa.tentativas >= 5:
                tentativa.bloqueado_ate = now + timedelta(minutes=30)
            db.session.commit()
            flash('Não foi possível validar o cadastro. Confira os dados e tente novamente.', 'danger')
            return _render_signup(organizacao), 400
        if tentativa:
            db.session.delete(tentativa)
        PortalCadastro.query.filter_by(tenant_id=organizacao.id, servidor_id=servidor.id,
                                      confirmado_em=None).delete()
        pending = PortalCadastro(tenant_id=organizacao.id, servidor_id=servidor.id,
                                 email=email, telefone=telefone, endereco=endereco,
                                 senha_hash=bcrypt.generate_password_hash(senha).decode('utf-8'),
                                 codigo_hash='0' * 64, expira_em=_portal_now() + timedelta(minutes=15))
        db.session.add(pending)
        db.session.flush()
        code = f'{secrets.randbelow(1000000):06d}'
        pending.codigo_hash = _email_code_hash(pending.id, code)
        try:
            _send_account_email(email, 'Confirme seu cadastro no Sysprot',
                                f'Seu código de confirmação é {code}. Ele expira em 15 minutos.')
        except (RuntimeError, OSError, smtplib.SMTPException):
            db.session.rollback()
            flash('Não foi possível enviar o código agora. Tente novamente mais tarde.', 'danger')
            return _render_signup(organizacao), 503
        db.session.commit()
        session['portal_cadastro_id'] = pending.id
        session.pop('portal_identificacao', None)
        return redirect(tenant_entry_url('portal_confirmar_cadastro', organizacao))
    return _render_signup(organizacao)


@app.route('/portal/<string:slug>/confirmar-cadastro', methods=['GET', 'POST'])
def portal_confirmar_cadastro(slug):
    organizacao = Organizacao.query.filter_by(slug=slug.strip().lower(), ativo=True,
                                               portal_servidor_remoto_enabled=True).first_or_404()
    pending = PortalCadastro.query.filter_by(id=session.get('portal_cadastro_id'),
                                             tenant_id=organizacao.id, confirmado_em=None).first()
    expiry = pending.expira_em.replace(tzinfo=timezone.utc) if pending and pending.expira_em.tzinfo is None else (pending.expira_em if pending else None)
    if not pending or expiry <= _portal_now() or pending.tentativas >= 5:
        session.pop('portal_cadastro_id', None)
        flash('O código expirou ou o limite de tentativas foi atingido. Inicie um novo cadastro.', 'warning')
        return redirect(tenant_entry_url('portal_cadastro', organizacao))
    if request.method == 'POST':
        code = (request.form.get('codigo') or '').strip()
        pending.tentativas += 1
        if not re.fullmatch(r'\d{6}', code) or not hmac.compare_digest(pending.codigo_hash, _email_code_hash(pending.id, code)):
            db.session.commit()
            flash('Código inválido.', 'danger')
            return render_template('portal_confirmar_cadastro.html', organizacao=organizacao), 400
        servidor = db.session.get(Servidor, pending.servidor_id)
        if Usuario.query.filter_by(tenant_id=organizacao.id, servidor_id=servidor.id).first():
            abort(409, description='Esta matrícula já possui conta.')
        user = Usuario(tenant_id=organizacao.id, servidor_id=servidor.id,
                       nome=servidor.nome.split()[0], nome_completo=servidor.nome,
                       cpf=servidor.cpf, login=servidor.matricula, senha=pending.senha_hash,
                       tipo='requerente', status='ativo', email=pending.email,
                       telefone=pending.telefone, endereco=pending.endereco)
        db.session.add(user)
        pending.confirmado_em = _portal_now()
        db.session.commit()
        session.pop('portal_cadastro_id', None)
        flash('Cadastro confirmado. Entre com sua matrícula e senha.', 'success')
        return redirect(tenant_entry_url('portal_login', organizacao))
    return render_template('portal_confirmar_cadastro.html', organizacao=organizacao)


@app.post('/admin/usuarios/<int:user_id>/recuperar-portal')
@permission_required('manage')
def admin_portal_recovery(user_id):
    user = tenant_get_or_404(Usuario, user_id)
    if user.tipo != 'requerente' or user.status != 'ativo' or not user.servidor_id:
        abort(400, description='A conta não está habilitada para o Portal do Servidor.')
    now = _portal_now()
    PortalRecuperacao.query.filter_by(tenant_id=current_tenant_id(), usuario_id=user.id,
                                      utilizado_em=None).update({'utilizado_em': now})
    token = secrets.token_urlsafe(32)
    db.session.add(PortalRecuperacao(
        tenant_id=current_tenant_id(), usuario_id=user.id,
        token_hash=_portal_token_hash(token), gerado_por_id=current_user.id,
        expira_em=now + timedelta(minutes=30)))
    db.session.commit()
    link = tenant_entry_url('portal_recuperar', active_organization(), token=token, external=True)
    return render_template('portal_recuperacao_link.html', user=user, link=link)


@app.route('/portal/<string:slug>/recuperar/<string:token>', methods=['GET', 'POST'])
def portal_recuperar(slug, token):
    organizacao = Organizacao.query.filter_by(slug=slug.strip().lower(), ativo=True,
                                               portal_servidor_remoto_enabled=True).first_or_404()
    record = PortalRecuperacao.query.filter_by(
        tenant_id=organizacao.id, token_hash=_portal_token_hash(token),
        utilizado_em=None).first()
    expiry = record.expira_em.replace(tzinfo=timezone.utc) if record and record.expira_em.tzinfo is None else (record.expira_em if record else None)
    if not record or expiry <= _portal_now():
        return render_template('portal_recuperar.html', organizacao=organizacao,
                               expired=True), 410
    if request.method == 'POST':
        password = request.form.get('senha') or ''
        confirmation = request.form.get('confirmar_senha') or ''
        if not _portal_password_valid(password) or password != confirmation:
            flash('A senha deve ter pelo menos 8 caracteres, letras minúsculas, maiúsculas e um número. Confira também a confirmação.', 'danger')
        else:
            user = Usuario.query.filter_by(id=record.usuario_id, tenant_id=organizacao.id,
                                           tipo='requerente', status='ativo').first_or_404()
            user.senha = bcrypt.generate_password_hash(password).decode('utf-8')
            record.utilizado_em = _portal_now()
            PortalSessao.query.filter_by(tenant_id=organizacao.id, usuario_id=user.id,
                                         encerrada_em=None).update({'encerrada_em': _portal_now()})
            db.session.commit()
            session.pop('portal_session_token', None)
            session.pop('auth_surface', None)
            logout_user()
            flash('Senha definida. Entre com a nova senha.', 'success')
            return redirect(tenant_entry_url('portal_login', organizacao))
    return render_template('portal_recuperar.html', organizacao=organizacao, expired=False)


@app.get('/portal')
@portal_required
def portal_home():
    protocolos = accessible_protocols_query().order_by(Protocolo.id.desc()).all()
    pendencias = tenant_query(SolicitacaoComplemento).filter(
        SolicitacaoComplemento.status == 'PENDENTE',
        SolicitacaoComplemento.protocolo_id.in_([p.id for p in protocolos] or [-1])).count()
    return render_template('portal_home.html', protocolos=protocolos, pendencias=pendencias,
                           organizacao=active_organization())


@app.get('/portal/sessoes')
@portal_required
def portal_sessoes():
    records = PortalSessao.query.filter_by(
        tenant_id=current_tenant_id(), usuario_id=current_user.id,
        encerrada_em=None).order_by(PortalSessao.criada_em.desc()).all()
    current = _portal_session()
    return render_template('portal_sessoes.html', organizacao=active_organization(),
                           records=records, current_id=current.id if current else None,
                           now=_portal_now())


@app.post('/portal/sessoes/<int:session_id>/encerrar')
@portal_required
def portal_encerrar_sessao(session_id):
    record = PortalSessao.query.filter_by(
        id=session_id, tenant_id=current_tenant_id(), usuario_id=current_user.id,
        encerrada_em=None).first_or_404()
    current = _portal_session()
    current_session = current is not None and current.id == record.id
    record.encerrada_em = _portal_now()
    db.session.commit()
    if current_session:
        organization = active_organization()
        session.pop('portal_session_token', None)
        session.pop('auth_surface', None)
        logout_user()
        return redirect(tenant_entry_url('portal_login', organization))
    flash('Acesso encerrado.', 'success')
    return redirect(url_for('portal_sessoes'))


@app.route('/portal/novo', methods=['GET', 'POST'])
@portal_required
def portal_novo_protocolo():
    servidor = current_user.servidor
    tipos = tenant_query(TipoRequerimento).filter_by(ativo=True).order_by(TipoRequerimento.nome).all()
    if request.method == 'GET':
        return render_template('portal_novo.html', servidor=servidor, tipos=tipos,
                               organizacao=active_organization())
    tipo = (request.form.get('tipo_requerimento') or '').strip()
    observacoes = (request.form.get('observacoes') or '').strip()
    declaracao_aceita = request.form.get('declaracao') == 'on'
    if not declaracao_aceita or not observacoes or not tenant_query(TipoRequerimento).filter_by(nome=tipo, ativo=True).first():
        flash('Selecione o tipo, descreva o pedido e confirme a declaração de envio.', 'danger')
        return render_template('portal_novo.html', servidor=servidor, tipos=tipos,
                               organizacao=active_organization()), 400
    try:
        uploads = validated_uploads(request.files.getlist('anexos'))
    except ValueError as error:
        flash(str(error), 'danger')
        return render_template('portal_novo.html', servidor=servidor, tipos=tipos,
                               organizacao=active_organization()), 400
    numero = gerar_proximo_numero_protocolo()
    setor = tenant_query(Lotacao).filter_by(nome=servidor.lotacao, ativo=True).first() if servidor.lotacao else None
    protocolo = Protocolo(
        tenant_id=current_tenant_id(), numero=numero, nome=servidor.nome,
        matricula=servidor.matricula, cargo=servidor.cargo, lotacao=servidor.lotacao,
        unidade_exercicio=servidor.unidade_de_exercicio, tipo_requerimento=tipo,
        requer_ao=(request.form.get('requer_ao') or '').strip() or None,
        observacoes=observacoes, data_solicitacao=datetime.now().date(),
        responsavel=current_user.login, criado_por_id=current_user.id,
        requerente_servidor_id=servidor.id, modalidade_abertura='remota_requerente',
        setor_atual_id=setor.id if setor else None, status='PROTOCOLO GERADO')
    db.session.add(protocolo)
    db.session.flush()
    db.session.add(HistoricoProtocolo(
        tenant_id=current_tenant_id(), protocolo_id=protocolo.id, status=protocolo.status,
        responsavel=current_user.login, usuario_id=current_user.id, acao='ENVIO_REMOTO',
        observacao='Requerimento enviado pelo próprio servidor em conta individual vinculada ao cadastro funcional.'))
    for index, (filename, data, mime_type) in enumerate(uploads, start=1):
        chave = f'anexo-inicial-{uuid.uuid4().hex[:12]}'
        storage_path, backend, digest, stored_data = store_attachment_bytes(
            data, current_tenant_id(), protocolo.id, chave, 1, filename, mime_type)
        db.session.add(Anexo(
            tenant_id=current_tenant_id(), protocolo_id=protocolo.id, file_name=filename,
            storage_path=storage_path, storage_backend=backend, file_hash=digest,
            file_size=len(data), mime_type=mime_type, file_data=stored_data,
            documento_chave=chave, versao=1, enviado_por_id=current_user.id))
    db.session.flush()
    token, codigo = secrets.token_urlsafe(32), _public_code()
    while EmissaoEletronica.query.filter(or_(EmissaoEletronica.token_publico == token,
                                             EmissaoEletronica.codigo_publico == codigo)).first():
        token, codigo = secrets.token_urlsafe(32), _public_code()
    origem = request.remote_addr or ''
    emissao = EmissaoEletronica(
        tenant_id=current_tenant_id(), protocolo_id=protocolo.id,
        emitido_por_id=current_user.id, pdf_anexo_id=0, versao=1,
        token_publico=token, codigo_publico=codigo, pdf_sha256='0' * 64,
        metodo='conta_individual', nivel_garantia='interno',
        declaracao='Requerimento enviado eletronicamente pelo próprio requerente autenticado em conta individual vinculada ao cadastro funcional.',
        nome_emitente=servidor.nome, login_emitente=current_user.login,
        ip_hash=hmac.new(app.config['SECRET_KEY'].encode(), origem.encode(), hashlib.sha256).hexdigest(),
        user_agent_hash=hashlib.sha256((request.user_agent.string or '').encode()).hexdigest(),
        emitido_em=datetime.now().astimezone(), status='VALIDA')
    pdf_bytes = render_protocol_pdf(protocolo, emissao)
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    filename = f'protocolo_{numero.replace("/", "-")}_envio_remoto_v1.pdf'
    storage_path, backend, stored_hash, stored_data = store_attachment_bytes(
        pdf_bytes, current_tenant_id(), protocolo.id, 'protocolo-autenticado', 1,
        filename, 'application/pdf')
    if not hmac.compare_digest(digest, stored_hash):
        db.session.rollback()
        abort(500, description='Falha ao confirmar a integridade do requerimento enviado.')
    documento = Anexo(
        tenant_id=current_tenant_id(), protocolo_id=protocolo.id, file_name=filename,
        storage_path=storage_path, storage_backend=backend, file_hash=digest,
        file_size=len(pdf_bytes), mime_type='application/pdf', file_data=stored_data,
        documento_chave='protocolo-autenticado', versao=1, enviado_por_id=current_user.id)
    db.session.add(documento)
    db.session.flush()
    emissao.pdf_anexo_id = documento.id
    emissao.pdf_sha256 = digest
    db.session.add(emissao)
    db.session.commit()
    flash(f'Requerimento enviado. Protocolo {numero} gerado com sucesso.', 'success')
    return redirect(url_for('portal_detalhe', protocolo_id=protocolo.id))


@app.get('/portal/protocolo/<int:protocolo_id>')
@portal_required
def portal_detalhe(protocolo_id):
    protocolo = accessible_protocol_or_404(protocolo_id)
    return render_template('portal_detalhe.html', protocolo=protocolo, organizacao=active_organization())


@app.post('/portal/protocolo/<int:protocolo_id>/complemento/<int:solicitacao_id>')
@portal_required
def portal_enviar_complemento(protocolo_id, solicitacao_id):
    protocolo = accessible_protocol_or_404(protocolo_id)
    solicitacao = tenant_query(SolicitacaoComplemento).filter_by(
        id=solicitacao_id, protocolo_id=protocolo.id, status='PENDENTE').first_or_404()
    try:
        uploads = validated_uploads(request.files.getlist('anexos'))
    except ValueError as error:
        flash(str(error), 'danger')
        return redirect(url_for('portal_detalhe', protocolo_id=protocolo.id))
    if not uploads:
        flash('Selecione ao menos um documento para atender à solicitação.', 'danger')
        return redirect(url_for('portal_detalhe', protocolo_id=protocolo.id))
    for filename, data, mime_type in uploads:
        chave = f'complemento-{solicitacao.id}-{uuid.uuid4().hex[:12]}'
        path, backend, digest, stored_data = store_attachment_bytes(
            data, current_tenant_id(), protocolo.id, chave, 1, filename, mime_type)
        db.session.add(Anexo(
            tenant_id=current_tenant_id(), protocolo_id=protocolo.id, file_name=filename,
            storage_path=path, storage_backend=backend, file_hash=digest,
            file_size=len(data), mime_type=mime_type, file_data=stored_data,
            documento_chave=chave, versao=1, enviado_por_id=current_user.id,
            solicitacao_complemento_id=solicitacao.id))
    solicitacao.status = 'ATENDIDA'
    solicitacao.atendido_em = datetime.now().astimezone()
    solicitacao.atendido_por_id = current_user.id
    db.session.add(HistoricoProtocolo(
        tenant_id=current_tenant_id(), protocolo_id=protocolo.id, status=protocolo.status,
        responsavel=current_user.login, usuario_id=current_user.id,
        acao='COMPLEMENTO_ENVIADO',
        observacao=f'Solicitação de complemento #{solicitacao.id} atendida com {len(uploads)} arquivo(s).'))
    db.session.commit()
    flash('Documentação complementar enviada e registrada sem alterar o requerimento original.', 'success')
    return redirect(url_for('portal_detalhe', protocolo_id=protocolo.id))


@app.post('/portal/sair')
@portal_required
def portal_logout():
    organization = active_organization()
    record = _portal_session()
    if record:
        record.encerrada_em = _portal_now()
        db.session.commit()
    session.pop('portal_session_token', None)
    session.pop('auth_surface', None)
    logout_user()
    flash('Você saiu do Portal do Servidor.', 'info')
    return redirect(tenant_entry_url('portal_login', organization))


@app.route("/login", methods=['GET', 'POST'])
def login():
    """Entrada legada e exclusiva para localizar contas de administrador geral.

    Usuários dos clientes devem receber o endereço /entrar/<slug>, no qual a
    organização já está definida e não é solicitada na tela.
    """
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        agora = datetime.utcnow()
        fingerprint = login_fingerprint(form.organizacao.data, form.login.data)
        tentativa = LoginTentativa.query.filter_by(identificador_hash=fingerprint).with_for_update().first()
        if tentativa and tentativa.bloqueado_ate and tentativa.bloqueado_ate > agora:
            flash('Não foi possível autenticar. Aguarde alguns minutos e tente novamente.', 'danger')
            return render_template('login.html', title='Login', form=form), 429
        if tentativa and tentativa.janela_iniciada_em < agora - timedelta(minutes=15):
            tentativa.tentativas = 0
            tentativa.janela_iniciada_em = agora
            tentativa.bloqueado_ate = None
        organizacao = Organizacao.query.filter_by(slug=form.organizacao.data.strip().lower(), ativo=True).first()
        user = Usuario.query.filter_by(
            tenant_id=organizacao.id if organizacao else None,
            login=form.login.data,
            status='ativo'
        ).first()
        if user and user.tipo != 'requerente' and bcrypt.check_password_hash(user.senha, form.senha.data):
            if tentativa:
                db.session.delete(tentativa)
                db.session.commit()
            login_user(user, remember=form.remember.data)
            session['auth_surface'] = 'backoffice'
            next_page = request.args.get('next')
            flash('Login bem-sucedido!', 'success')
            destination = safe_local_redirect(next_page)
            if user.is_platform_admin:
                session.pop('active_tenant_id', None)
                destination = url_for('platform_organizations')
            return redirect(destination or url_for('home'))
        else:
            if not tentativa:
                tentativa = LoginTentativa(identificador_hash=fingerprint, tentativas=0,
                                            janela_iniciada_em=agora)
                db.session.add(tentativa)
            tentativa.tentativas += 1
            if tentativa.tentativas >= 5:
                tentativa.bloqueado_ate = agora + timedelta(minutes=30)
            db.session.commit()
            flash('Não foi possível autenticar. Verifique os dados informados.', 'danger')
    return render_template('login.html', title='Login', form=form)


@app.post("/logout")
@login_required
def logout():
    session.pop('active_tenant_id', None)
    session.pop('auth_surface', None)
    logout_user()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('login'))

@app.route("/meus_protocolos")
@login_required
def meus_protocolos():
    page = request.args.get('page', 1, type=int)
    query = apply_protocol_filters(
        accessible_protocols_query().filter_by(responsavel=current_user.login),
        request.args,
    )
    protocolos = query\
        .order_by(Protocolo.id.desc())\
        .paginate(page=page, per_page=10)
    return render_template(
        'protocolos.html', protocolos=protocolos, title="Meus Protocolos",
        list_endpoint='meus_protocolos',
        pagination_args=pagination_filter_args(request.args),
    )

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.tipo != 'admin':
            flash('Acesso negado. Requer permissão de administrador.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function


@app.get('/admin/auditoria')
@login_required
@admin_required
def admin_auditoria():
    valid, records, broken_at = verify_audit_chain(current_tenant_id())
    if request.args.get('exportar') == '1':
        body = json.dumps({
            'organizacao_id': current_tenant_id(), 'integra': valid,
            'primeira_falha': broken_at, 'eventos': [{
                'sequencia': item.sequencia, 'payload': json.loads(item.payload),
                'hash_anterior': item.hash_anterior, 'hash_atual': item.hash_atual,
            } for item in records],
        }, ensure_ascii=False, indent=2)
        response = Response(body, mimetype='application/json')
        response.headers['Content-Disposition'] = 'attachment; filename="auditoria-sysprot.json"'
        return response
    return render_template('auditoria.html', valid=valid, broken_at=broken_at,
                           records=records, title='Auditoria de protocolos')

def platform_admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_platform_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def require_platform_tenant_selection():
    if not current_user.is_authenticated or not current_user.is_platform_admin:
        return None
    allowed = {'platform_organizations', 'platform_select_organization', 'platform_create_admin',
               'platform_set_subdomain', 'logout',
               'trocar_senha_inicial', 'configurar_pin', 'solicitar_redefinicao_pin',
               'platform_update_capabilities',
               'support_list', 'support_create', 'support_detail', 'support_reply',
               'support_assign', 'support_update_status',
               'health', 'static', 'organization_logo'}
    if request.endpoint in allowed:
        return None
    selected = session.get('active_tenant_id')
    if not selected or not Organizacao.query.filter_by(id=selected, ativo=True).first():
        session.pop('active_tenant_id', None)
        return redirect(url_for('platform_organizations'))
    return None


@app.before_request
def isolate_portal_surface():
    if not current_user.is_authenticated or current_user.tipo != 'requerente':
        return None
    allowed = {'portal_home', 'portal_novo_protocolo', 'portal_detalhe',
               'portal_enviar_complemento', 'portal_logout',
               'portal_sessoes', 'portal_encerrar_sessao',
               'baixar_anexo', 'gerar_pdf_protocolo', 'organization_logo', 'static',
               'validar_emissao', 'health'}
    if session.get('auth_surface') != 'portal':
        session.pop('auth_surface', None)
        logout_user()
        abort(403)
    if request.endpoint not in allowed:
        return redirect(url_for('portal_home'))
    return None


@app.before_request
def exigir_troca_senha_inicial():
    if (current_user.is_authenticated and current_user.tipo != 'requerente'
            and current_user.deve_trocar_senha
            and request.endpoint not in {'trocar_senha_inicial', 'logout', 'static', 'organization_logo'}):
        return redirect(url_for('trocar_senha_inicial'))
    return None


@app.route('/minha-conta/trocar-senha', methods=['GET', 'POST'])
@login_required
def trocar_senha_inicial():
    if current_user.tipo == 'requerente':
        abort(403)
    if request.method == 'POST':
        atual = request.form.get('senha_atual') or ''
        nova = request.form.get('senha_nova') or ''
        if (not bcrypt.check_password_hash(current_user.senha, atual)
                or not _strong_password(nova) or nova != request.form.get('confirmar_senha')
                or bcrypt.check_password_hash(current_user.senha, nova)):
            flash('Confira a senha atual e escolha uma nova senha com pelo menos 12 caracteres.', 'danger')
        else:
            current_user.senha = bcrypt.generate_password_hash(nova).decode('utf-8')
            current_user.deve_trocar_senha = False
            db.session.commit()
            login_user(current_user._get_current_object(), remember=False)
            flash('Senha alterada. Agora configure seu PIN pessoal de emissão.', 'success')
            return redirect(url_for('configurar_pin'))
    return render_template('trocar_senha_inicial.html')


@app.route('/minha-conta/pin', methods=['GET', 'POST'])
@login_required
def configurar_pin():
    if current_user.tipo not in {'admin', 'protocolista'}:
        abort(403)
    if request.method == 'POST':
        pin = (request.form.get('pin') or '').strip()
        password = request.form.get('senha') or ''
        code = (request.form.get('codigo') or '').strip()
        initial = not current_user.pin_hash
        if not re.fullmatch(r'\d{6}', pin):
            flash('O PIN deve conter exatamente seis números.', 'danger')
        elif initial and not bcrypt.check_password_hash(current_user.senha, password):
            flash('Senha incorreta.', 'danger')
        elif not initial and (current_user.pin_redefinicao_erros >= 5 or
                              not current_user.pin_redefinicao_hash or
                              not current_user.pin_redefinicao_expira_em or
                              _portal_now() > _as_aware(current_user.pin_redefinicao_expira_em) or
                              not hmac.compare_digest(current_user.pin_redefinicao_hash,
                                                      _email_code_hash(current_user.id, code))):
            current_user.pin_redefinicao_erros += 1
            db.session.commit()
            flash('Código de redefinição inválido ou expirado.', 'danger')
        else:
            current_user.pin_hash = bcrypt.generate_password_hash(pin).decode('utf-8')
            current_user.pin_erros = 0
            current_user.pin_bloqueado_ate = None
            current_user.pin_redefinicao_hash = None
            current_user.pin_redefinicao_expira_em = None
            current_user.pin_redefinicao_erros = 0
            db.session.commit()
            flash('PIN pessoal configurado.', 'success')
            return redirect(url_for('home'))
    return render_template('configurar_pin.html')


@app.post('/minha-conta/pin/redefinir')
@login_required
def solicitar_redefinicao_pin():
    if current_user.tipo not in {'admin', 'protocolista'} or not current_user.email:
        abort(403)
    if (current_user.pin_redefinicao_expira_em and
            _as_aware(current_user.pin_redefinicao_expira_em) > _portal_now()):
        flash('Já existe um código válido. Aguarde sua expiração antes de pedir outro.', 'warning')
        return redirect(url_for('configurar_pin'))
    code = f'{secrets.randbelow(1000000):06d}'
    current_user.pin_redefinicao_hash = _email_code_hash(current_user.id, code)
    current_user.pin_redefinicao_expira_em = _portal_now() + timedelta(minutes=15)
    current_user.pin_redefinicao_erros = 0
    try:
        _send_account_email(current_user.email, 'Redefinição do PIN do Sysprot',
                            f'Seu código para redefinir o PIN é {code}. Ele expira em 15 minutos.')
    except (RuntimeError, OSError, smtplib.SMTPException):
        db.session.rollback()
        flash('Não foi possível enviar o código agora.', 'danger')
        return redirect(url_for('configurar_pin'))
    db.session.commit()
    flash('Enviamos um código temporário para o e-mail cadastrado.', 'success')
    return redirect(url_for('configurar_pin'))

@app.get('/plataforma')
@platform_admin_required
def platform_organizations():
    organizations = Organizacao.query.order_by(Organizacao.nome).all()
    platform_form = PlatformAdminCreationForm()
    platform_form.organizacao_id.choices = [(item.id, item.nome) for item in organizations if item.ativo]
    summaries = []
    for organization in organizations:
        summaries.append({
            'organization': organization,
            'users': Usuario.query.filter_by(tenant_id=organization.id, status='ativo').count(),
            'protocols': Protocolo.query.filter_by(tenant_id=organization.id).count(),
            'selected': session.get('active_tenant_id') == organization.id,
        })
    platform_admins = Usuario.query.filter_by(is_platform_admin=True).order_by(Usuario.nome_completo).all()
    return render_template('plataforma.html', title='Administração da plataforma', summaries=summaries,
                           platform_form=platform_form, platform_admins=platform_admins)

@app.post('/plataforma/administradores/novo')
@platform_admin_required
def platform_create_admin():
    organizations = Organizacao.query.filter_by(ativo=True).order_by(Organizacao.nome).all()
    form = PlatformAdminCreationForm()
    form.organizacao_id.choices = [(item.id, item.nome) for item in organizations]
    if not form.validate_on_submit():
        flash('Verifique os dados do novo administrador geral.', 'danger')
        return redirect(url_for('platform_organizations'))
    organization = Organizacao.query.filter_by(id=form.organizacao_id.data, ativo=True).first_or_404()
    if Usuario.query.filter_by(tenant_id=organization.id, login=form.login.data.strip()).first():
        flash('Esse login já existe na organização selecionada.', 'danger')
        return redirect(url_for('platform_organizations'))
    user = Usuario(
        tenant_id=organization.id, nome=form.nome_completo.data.strip().split()[0],
        nome_completo=form.nome_completo.data.strip(), login=form.login.data.strip(),
        email=form.email.data.strip(),
        senha=bcrypt.generate_password_hash(form.senha.data).decode('utf-8'),
        tipo='admin', is_platform_admin=True, status='ativo', deve_trocar_senha=True)
    db.session.add(user)
    db.session.commit()
    flash('Administrador geral criado com sucesso.', 'success')
    return redirect(url_for('platform_organizations'))

@app.post('/plataforma/cliente/<int:organization_id>')
@platform_admin_required
def platform_select_organization(organization_id):
    organization = Organizacao.query.filter_by(id=organization_id, ativo=True).first_or_404()
    session['active_tenant_id'] = organization.id
    session.modified = True
    db.session.add(HistoricoProtocolo(
        tenant_id=organization.id, usuario_id=current_user.id,
        acao='ACESSO_ADMINISTRADOR_GERAL', responsavel=current_user.login,
        observacao='Administrador geral selecionou este cliente para acesso administrativo.'))
    db.session.commit()
    flash(f'Cliente ativo: {organization.nome}.', 'info')
    return redirect(url_for('home'))


@app.post('/plataforma/cliente/<int:organization_id>/subdominio')
@platform_admin_required
def platform_set_subdomain(organization_id):
    organization = Organizacao.query.filter_by(id=organization_id).first_or_404()
    label = (request.form.get('subdominio') or '').strip().lower()
    if label and (not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
                  or label in _RESERVED_SUBDOMAINS):
        flash('Subdomínio inválido ou reservado.', 'danger')
        return redirect(url_for('platform_organizations'))
    if label and Organizacao.query.filter(
            Organizacao.id != organization.id,
            or_(Organizacao.subdominio == label, Organizacao.slug == label)).first():
        flash('Esse subdomínio já identifica outro cliente.', 'danger')
        return redirect(url_for('platform_organizations'))
    alias = OrganizacaoSubdominioAlias.query.filter_by(subdominio=label).first() if label else None
    if alias and alias.organizacao_id != organization.id:
        flash('Esse endereço anterior pertence a outro cliente.', 'danger')
        return redirect(url_for('platform_organizations'))
    if alias:
        db.session.delete(alias)
    if organization.subdominio and organization.subdominio != label:
        db.session.add(OrganizacaoSubdominioAlias(
            organizacao_id=organization.id, subdominio=organization.subdominio))
    organization.subdominio = label or None
    db.session.commit()
    flash('Endereço do cliente atualizado.', 'success')
    return redirect(url_for('platform_organizations'))


@app.post('/plataforma/cliente/<int:organization_id>/capacidades')
@platform_admin_required
def platform_update_capabilities(organization_id):
    organization = Organizacao.query.filter_by(id=organization_id).first_or_404()
    electronic_enabled = request.form.get('emissao_eletronica_protocolista_enabled') == 'on'
    remote_enabled = request.form.get('portal_servidor_remoto_enabled') == 'on'
    reason = (request.form.get('motivo') or '').strip()[:500] or None

    organization.emissao_eletronica_protocolista_enabled = electronic_enabled
    organization.portal_servidor_remoto_enabled = remote_enabled
    db.session.add(OrganizacaoCapacidadeEvento(
        organizacao_id=organization.id,
        alterado_por_id=current_user.id,
        emissao_eletronica_protocolista_enabled=electronic_enabled,
        portal_servidor_remoto_enabled=remote_enabled,
        nivel_garantia_assinatura='interno',
        motivo=reason,
    ))
    db.session.commit()
    flash(f'Capacidades de {organization.nome} atualizadas e auditadas.', 'success')
    return redirect(url_for('platform_organizations'))

@app.route("/relatorios")
@permission_required('reports')
def relatorios():
    # This route essentially does the same as listar_protocolos but renders a different template
    # to match the original app's structure.
    page = request.args.get('page', 1, type=int)
    query = apply_protocol_filters(accessible_protocols_query(), request.args)
    protocolos = query.order_by(Protocolo.id.desc()).paginate(page=page, per_page=10)
    return render_template('relatorios.html', protocolos=protocolos, title="Relatórios",
                           pagination_args=pagination_filter_args(request.args))

# --- Rotas de Configuração (Admin) ---

@app.route("/configuracoes", methods=['GET', 'POST'])
@login_required
@admin_required
def configuracoes():
    user_form = AdminUserCreationForm()
    lotacao_form = AdminListItemForm()
    tipo_form = AdminListItemForm()
    branding_form = BrandingForm()

    if user_form.validate_on_submit() and user_form.submit.data:
        # Lógica de criação de usuário movida para uma rota de API dedicada
        pass

    lotacoes = tenant_query(Lotacao).all()
    user_form.lotacao_id.choices = [(0, 'Sem setor definido')] + [(item.id, item.nome) for item in lotacoes if item.ativo]
    servidores = tenant_query(Servidor).order_by(Servidor.nome, Servidor.matricula).all()
    user_form.servidor_id.choices = [(0, 'Sem vínculo funcional')] + [
        (item.id, f'{item.nome} — matrícula {item.matricula}') for item in servidores]
    users = tenant_query(Usuario).filter_by(is_platform_admin=False).all()
    tipos = tenant_query(TipoRequerimento).all()

    return render_template('configuracoes.html', title="Configurações",
                           users=users, lotacoes=lotacoes, tipos=tipos,
                           user_form=user_form, lotacao_form=lotacao_form, tipo_form=tipo_form,
                            branding_form=branding_form, organizacao=active_organization(), servidores=servidores)

@app.post('/admin/identidade/logo')
@login_required
@admin_required
def admin_update_logo():
    from PIL import Image, UnidentifiedImageError

    form = BrandingForm()
    organizacao = active_organization()
    organizacao.municipio = (request.form.get('municipio') or '').strip() or None
    organizacao.orgao = (request.form.get('orgao') or '').strip() or None
    organizacao.rodape_documento = (request.form.get('rodape_documento') or '').strip() or None
    if form.remover.data and form.validate():
        organizacao.logo_data = None
        organizacao.logo_mime_type = None
        organizacao.logo_nome_arquivo = None
        organizacao.logo_atualizada_em = datetime.utcnow()
        db.session.commit()
        flash('Logo padrão restaurada.', 'success')
        return redirect(url_for('configuracoes'))
    if not form.validate_on_submit():
        flash('Verifique os dados e a imagem informados.', 'danger')
        return redirect(url_for('configuracoes'))
    if not form.logo.data:
        db.session.commit()
        flash('Dados institucionais atualizados.', 'success')
        return redirect(url_for('configuracoes'))
    arquivo = form.logo.data
    arquivo.stream.seek(0, os.SEEK_END)
    tamanho = arquivo.stream.tell()
    arquivo.stream.seek(0)
    if tamanho > 5 * 1024 * 1024:
        flash('A imagem deve ter no máximo 5 MB.', 'danger')
        return redirect(url_for('configuracoes'))
    try:
        saida = normalize_logo_png(arquivo.stream)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        flash('O arquivo enviado não é uma imagem válida ou excede os limites de segurança.', 'danger')
        return redirect(url_for('configuracoes'))
    if saida.getbuffer().nbytes > 2 * 1024 * 1024:
        flash('Após o processamento, a logo excedeu 2 MB. Utilize uma imagem mais simples.', 'danger')
        return redirect(url_for('configuracoes'))
    organizacao.logo_data = saida.read()
    organizacao.logo_mime_type = 'image/png'
    organizacao.logo_nome_arquivo = secure_filename(arquivo.filename or 'logo.png')
    organizacao.logo_atualizada_em = datetime.utcnow()
    db.session.commit()
    flash('Identidade visual atualizada em todo o sistema.', 'success')
    return redirect(url_for('configuracoes'))

@app.route("/admin/usuarios/novo", methods=['POST'])
@login_required
@admin_required
def admin_create_user():
    form = AdminUserCreationForm()
    lotacoes = tenant_query(Lotacao).filter_by(ativo=True).order_by(Lotacao.nome).all()
    form.lotacao_id.choices = [(0, 'Sem setor definido')] + [(item.id, item.nome) for item in lotacoes]
    servidores = tenant_query(Servidor).order_by(Servidor.nome, Servidor.matricula).all()
    form.servidor_id.choices = [(0, 'Sem vínculo funcional')] + [
        (item.id, f'{item.nome} — matrícula {item.matricula}') for item in servidores]
    if form.validate_on_submit():
        servidor_id = form.servidor_id.data or None
        if form.tipo.data == 'requerente' and not servidor_id:
            flash('O usuário do Portal do Servidor deve estar vinculado a um cadastro funcional.', 'danger')
            return redirect(url_for('configuracoes'))
        if servidor_id and not tenant_query(Servidor).filter_by(id=servidor_id).first():
            abort(400, description='Cadastro funcional inválido.')
        if servidor_id and tenant_query(Usuario).filter_by(servidor_id=servidor_id).first():
            flash('Este cadastro funcional já está vinculado a outra conta.', 'danger')
            return redirect(url_for('configuracoes'))
        hashed_password = bcrypt.generate_password_hash(form.senha.data).decode('utf-8')
        user = Usuario(
            tenant_id=current_tenant_id(),
            nome_completo=form.nome_completo.data,
            login=form.login.data,
            email=form.email.data,
            senha=hashed_password,
            nome=form.nome_completo.data.split(' ')[0],
            tipo=form.tipo.data,
            status='ativo',
            deve_trocar_senha=form.tipo.data != 'requerente',
            lotacao_id=form.lotacao_id.data or None,
            servidor_id=servidor_id,
        )
        db.session.add(user)
        db.session.commit()
        flash('Usuário criado com sucesso!', 'success')
    else:
        flash('Erro ao criar usuário. Verifique os dados.', 'danger')
    return redirect(url_for('configuracoes'))


@app.post('/admin/servidores/importar')
@login_required
@admin_required
def admin_importar_servidores():
    upload = request.files.get('arquivo')
    if not upload or not upload.filename.lower().endswith('.xlsx'):
        flash('Selecione uma planilha .xlsx.', 'danger')
        return redirect(url_for('configuracoes'))
    data = upload.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        flash('A planilha deve ter até 2 MB.', 'danger')
        return redirect(url_for('configuracoes'))
    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        rows = workbook.active.iter_rows(values_only=True)
        header = [str(value or '').strip().lower() for value in next(rows)]
        required = ('matricula', 'nome', 'cpf', 'data_nascimento', 'nome_mae')
        if any(column not in header for column in required):
            raise ValueError('Colunas obrigatórias: matricula, nome, cpf, data_nascimento, nome_mae.')
        positions = {column: header.index(column) for column in required}
        parsed = []
        seen = set()
        for number, values in enumerate(rows, start=2):
            if number > 10001:
                raise ValueError('Limite de 10.000 servidores por arquivo.')
            if not any(value is not None for value in values):
                continue
            matricula_raw = values[positions['matricula']]
            matricula = (str(int(matricula_raw)) if isinstance(matricula_raw, (int, float))
                         and float(matricula_raw).is_integer() else str(matricula_raw or '').strip())
            nome = str(values[positions['nome']] or '').strip()
            cpf_raw = values[positions['cpf']]
            cpf = (str(int(cpf_raw)).zfill(11) if isinstance(cpf_raw, (int, float))
                   and float(cpf_raw).is_integer() else re.sub(r'\D', '', str(cpf_raw or '')))
            mae = str(values[positions['nome_mae']] or '').strip()
            raw_date = values[positions['data_nascimento']]
            nascimento = raw_date.date() if isinstance(raw_date, datetime) else (
                datetime.strptime(raw_date, '%d/%m/%Y').date() if isinstance(raw_date, str) else raw_date)
            if not matricula or not nome or len(cpf) != 11 or not mae or not nascimento or matricula in seen:
                raise ValueError(f'Dados inválidos ou matrícula repetida na linha {number}.')
            seen.add(matricula)
            parsed.append((matricula, nome, cpf, nascimento, mae))
        tenant = current_tenant_id()
        existing = {record.matricula: record for record in tenant_query(Servidor).filter(
            Servidor.matricula.in_(seen)).all()}
        for matricula, nome, cpf, nascimento, mae in parsed:
            record = existing.get(matricula)
            if record and tenant_query(Usuario).filter_by(servidor_id=record.id).first():
                continue
            if not record:
                record = Servidor(tenant_id=tenant, matricula=matricula)
                db.session.add(record)
            record.nome, record.cpf, record.nascimento, record.nome_mae = nome, cpf, nascimento, mae
        db.session.commit()
        flash(f'Planilha processada: {len(parsed)} matrícula(s). Contas já vinculadas foram preservadas.', 'success')
    except (ValueError, StopIteration, OSError, TypeError, IndexError, zipfile.BadZipFile) as error:
        db.session.rollback()
        flash(f'Importação não concluída: {error}', 'danger')
    return redirect(url_for('configuracoes'))

@app.post('/admin/usuarios/<int:user_id>/editar')
@login_required
@admin_required
def admin_update_user(user_id):
    user = tenant_get_or_404(Usuario, user_id)
    if user.is_platform_admin:
        abort(404)
    nome = (request.form.get('nome_completo') or '').strip()
    email = (request.form.get('email') or '').strip()
    tipo = (request.form.get('tipo') or '').strip()
    lotacao_raw = (request.form.get('lotacao_id') or '0').strip()
    servidor_raw = (request.form.get('servidor_id') or '0').strip()
    if not nome or not email or tipo not in ROLE_PERMISSIONS or not lotacao_raw.isdecimal() or not servidor_raw.isdecimal():
        abort(400, description='Dados de usuário inválidos.')
    lotacao_id = int(lotacao_raw) or None
    servidor_id = int(servidor_raw) or None
    if lotacao_id and not tenant_query(Lotacao).filter_by(id=lotacao_id, ativo=True).first():
        abort(400, description='Setor inválido ou inativo.')
    if servidor_id and not tenant_query(Servidor).filter_by(id=servidor_id).first():
        abort(400, description='Cadastro funcional inválido.')
    vinculo_existente = (tenant_query(Usuario).filter_by(servidor_id=servidor_id).first()
                         if servidor_id else None)
    if vinculo_existente and vinculo_existente.id != user.id:
        flash('Este cadastro funcional já está vinculado a outra conta.', 'danger')
        return redirect(url_for('configuracoes'))
    if tipo == 'requerente' and not servidor_id:
        flash('O usuário do Portal do Servidor deve estar vinculado a um cadastro funcional.', 'danger')
        return redirect(url_for('configuracoes'))
    if user.id == current_user.id and tipo != 'admin':
        flash('O administrador conectado não pode remover o próprio perfil administrativo.', 'warning')
        return redirect(url_for('configuracoes'))
    user.nome_completo = nome
    user.nome = nome.split()[0]
    user.email = email
    user.tipo = tipo
    user.lotacao_id = lotacao_id
    user.servidor_id = servidor_id
    db.session.commit()
    flash(f'Usuário {user.login} atualizado.', 'success')
    return redirect(url_for('configuracoes'))

@app.post('/admin/usuarios/<int:user_id>/status')
@login_required
@admin_required
def admin_toggle_user_status(user_id):
    user = tenant_get_or_404(Usuario, user_id)
    if user.is_platform_admin:
        abort(404)
    if user.id == current_user.id:
        flash('Não é possível desativar a própria conta durante o uso.', 'warning')
        return redirect(url_for('configuracoes'))
    novo_status = 'inativo' if user.status == 'ativo' else 'ativo'
    if novo_status == 'inativo' and user.tipo == 'admin':
        admins_ativos = tenant_query(Usuario).filter_by(tipo='admin', status='ativo').count()
        if admins_ativos <= 1:
            flash('A organização deve manter ao menos um administrador ativo.', 'warning')
            return redirect(url_for('configuracoes'))
    user.status = novo_status
    db.session.commit()
    flash(f'Usuário {user.login} {novo_status}.', 'success')
    return redirect(url_for('configuracoes'))

@app.route("/admin/item/<string:item_type>/novo", methods=['POST'])
@login_required
@admin_required
def admin_create_list_item(item_type):
    form = AdminListItemForm()
    if form.validate_on_submit():
        Model = None
        if item_type == 'lotacao':
            Model = Lotacao
        elif item_type == 'tipo':
            Model = TipoRequerimento

        if Model:
            new_item = Model(tenant_id=current_tenant_id(), nome=form.nome.data, ativo=True)
            db.session.add(new_item)
            db.session.commit()
            flash(f'{item_type.capitalize()} adicionado com sucesso!', 'success')
    else:
        flash('Erro ao adicionar item.', 'danger')
    return redirect(url_for('configuracoes'))

@app.route("/admin/item/<string:item_type>/<int:item_id>/status", methods=['POST'])
@login_required
@admin_required
def admin_toggle_item_status(item_type, item_id):
    Model = None
    if item_type == 'lotacao':
        Model = Lotacao
    elif item_type == 'tipo':
        Model = TipoRequerimento

    if Model:
        item = tenant_get_or_404(Model, item_id)
        item.ativo = not item.ativo
        db.session.commit()
        flash(f'Status do item alterado com sucesso!', 'success')
    return redirect(url_for('configuracoes'))

# --- Rota de Geração de PDF ---

def render_protocol_pdf(protocolo, emissao=None):
    import base64
    import qrcode
    from weasyprint import HTML
    organizacao = active_organization()
    version = int(organizacao.logo_atualizada_em.timestamp()) if organizacao.logo_atualizada_em else 0
    consulta_url = public_url('consulta_publica', consulta_token=protocolo.consulta_token)
    qr_consulta_buffer = io.BytesIO()
    qrcode.make(consulta_url).save(qr_consulta_buffer, format='PNG')
    qr_code_url = 'data:image/png;base64,' + base64.b64encode(qr_consulta_buffer.getvalue()).decode('ascii')
    qr_validacao_url = None
    if emissao:
        validacao_url = public_url('validar_emissao', token_publico=emissao.token_publico)
        qr_validacao_buffer = io.BytesIO()
        qrcode.make(validacao_url).save(qr_validacao_buffer, format='PNG')
        qr_validacao_url = ('data:image/png;base64,' +
                            base64.b64encode(qr_validacao_buffer.getvalue()).decode('ascii'))
    rendered_html = render_template(
        'pdf_template.html', protocolo=protocolo, organizacao=organizacao,
        pdf_logo_url=public_url('organization_logo', slug=organizacao.slug,
                                v=version), qr_code_url=qr_code_url,
        emissao=emissao, qr_validacao_url=qr_validacao_url)
    return HTML(string=rendered_html, base_url=request.base_url).write_pdf()

@app.route('/protocolo/<int:protocolo_id>/pdf')
@login_required
def gerar_pdf_protocolo(protocolo_id):
    protocolo = accessible_protocol_or_404(protocolo_id)
    if protocolo.emissao_eletronica:
        return _response_pdf_autenticado(protocolo.emissao_eletronica)
    pdf_bytes = render_protocol_pdf(protocolo)

    # Cria a resposta HTTP com o PDF
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=protocolo_{protocolo.numero.replace("/", "-")}.pdf'

    return response


def _response_pdf_autenticado(emissao):
    pdf_bytes = read_attachment_bytes(emissao.pdf_anexo)
    if not hmac.compare_digest(hashlib.sha256(pdf_bytes).hexdigest(), emissao.pdf_sha256):
        abort(409, description='A integridade do documento autenticado não pôde ser confirmada.')
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename={emissao.pdf_anexo.file_name}'
    response.headers['Cache-Control'] = 'private, no-store'
    return response


def _public_code():
    raw = secrets.token_hex(5).upper()
    return f'{raw[:5]}-{raw[5:]}'


@app.post('/protocolo/<int:protocolo_id>/autenticar-emissao')
@permission_required('create')
def autenticar_emissao_protocolo(protocolo_id):
    organizacao = active_organization()
    if not organizacao.emissao_eletronica_protocolista_enabled:
        abort(404)
    if current_user.tipo not in {'protocolista', 'admin'}:
        abort(403)
    protocolo = tenant_query(Protocolo).filter_by(id=protocolo_id).with_for_update().first_or_404()
    if protocolo.arquivado_em:
        abort(409, description='Processos arquivados não podem ser autenticados.')
    emissao_anterior = protocolo.emissao_eletronica
    if emissao_anterior and not protocolo.retificacao_pendente:
        return _response_pdf_autenticado(protocolo.emissao_eletronica)
    if not current_user.pin_hash:
        flash('Configure seu PIN pessoal antes de autenticar a emissão.', 'warning')
        return redirect(url_for('configurar_pin'))
    if not _confirmar_pin_usuario(current_user, request.form.get('pin') or ''):
        flash('PIN inválido ou temporariamente bloqueado. A emissão não foi autenticada.', 'danger')
        return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))

    token = secrets.token_urlsafe(32)
    codigo = _public_code()
    while EmissaoEletronica.query.filter(or_(EmissaoEletronica.token_publico == token,
                                             EmissaoEletronica.codigo_publico == codigo)).first():
        token, codigo = secrets.token_urlsafe(32), _public_code()
    declaracao = ('Protocolo emitido e autenticado eletronicamente pelo protocolista '
                  'mediante confirmação de seu PIN pessoal no Sysprot.')
    origem = request.remote_addr or ''
    nova_versao = (emissao_anterior.versao + 1) if emissao_anterior else 1
    emissao = EmissaoEletronica(
        tenant_id=current_tenant_id(), protocolo_id=protocolo.id,
        emitido_por_id=current_user.id, pdf_anexo_id=0,
        versao=nova_versao, substitui_emissao_id=emissao_anterior.id if emissao_anterior else None,
        token_publico=token, codigo_publico=codigo, pdf_sha256='0' * 64,
        metodo='pin_pessoal', nivel_garantia='interno', declaracao=declaracao,
        nome_emitente=current_user.nome_completo or current_user.nome,
        login_emitente=current_user.login,
        ip_hash=hmac.new(app.config['SECRET_KEY'].encode(), origem.encode(), hashlib.sha256).hexdigest(),
        user_agent_hash=hashlib.sha256((request.user_agent.string or '').encode()).hexdigest(),
        emitido_em=datetime.now().astimezone(), status='VALIDA')
    # O PDF inclui código/token e os dados congelados da evidência. O hash é calculado uma única vez.
    pdf_bytes = render_protocol_pdf(protocolo, emissao)
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    filename = f'protocolo_{protocolo.numero.replace("/", "-")}_autenticado_v{nova_versao}.pdf'
    storage_path, backend, stored_hash, stored_data = store_attachment_bytes(
        pdf_bytes, current_tenant_id(), protocolo.id, 'protocolo-autenticado', nova_versao,
        filename, 'application/pdf')
    if not hmac.compare_digest(digest, stored_hash):
        abort(500, description='Falha ao confirmar a integridade do documento.')
    documento = Anexo(
        tenant_id=current_tenant_id(), protocolo_id=protocolo.id, file_name=filename,
        storage_path=storage_path, storage_backend=backend, file_hash=digest,
        file_size=len(pdf_bytes), mime_type='application/pdf', file_data=stored_data,
        documento_chave='protocolo-autenticado', versao=nova_versao, enviado_por_id=current_user.id)
    db.session.add(documento)
    db.session.flush()
    emissao.pdf_anexo_id = documento.id
    emissao.pdf_sha256 = digest
    protocolo.emitido_por_usuario_id = current_user.id
    protocolo.retificacao_pendente = False
    if emissao_anterior:
        emissao_anterior.status = 'RETIFICADA'
    db.session.add_all([emissao, HistoricoProtocolo(
        tenant_id=current_tenant_id(), protocolo_id=protocolo.id, status=protocolo.status,
        responsavel=current_user.login, usuario_id=current_user.id,
        acao='RETIFICACAO_AUTENTICADA' if emissao_anterior else 'EMISSAO_AUTENTICADA',
        observacao=f'Versão autenticada v{nova_versao}, código {codigo}.')])
    db.session.commit()
    return _response_pdf_autenticado(emissao)


@app.route('/validar-emissao/<string:token_publico>', methods=['GET', 'POST'])
@csrf.exempt
def validar_emissao(token_publico):
    emissao = EmissaoEletronica.query.filter_by(token_publico=token_publico).first_or_404()
    arquivo_resultado = None
    if request.method == 'POST' and request.files.get('arquivo'):
        arquivo = request.files['arquivo']
        dados = arquivo.read(21 * 1024 * 1024 + 1)
        if len(dados) > 21 * 1024 * 1024:
            abort(413)
        arquivo_resultado = hmac.compare_digest(hashlib.sha256(dados).hexdigest(), emissao.pdf_sha256)
    return render_template('validar_emissao.html', emissao=emissao,
                           organizacao=db.session.get(Organizacao, emissao.tenant_id),
                           arquivo_resultado=arquivo_resultado)


@app.post('/protocolo/<int:protocolo_id>/cancelar-emissao')
@permission_required('edit')
def cancelar_emissao_protocolo(protocolo_id):
    organizacao = active_organization()
    if not organizacao.emissao_eletronica_protocolista_enabled:
        abort(404)
    if current_user.tipo not in {'protocolista', 'admin'}:
        abort(403)
    protocolo = tenant_query(Protocolo).filter_by(id=protocolo_id).with_for_update().first_or_404()
    emissao = protocolo.emissao_eletronica
    if not emissao or emissao.status != 'VALIDA':
        abort(409, description='Não existe uma emissão eletrônica vigente para cancelar.')
    if protocolo.retificacao_pendente:
        abort(409, description='Conclua ou descarte a retificação pendente antes do cancelamento.')
    senha = request.form.get('senha') or ''
    motivo = (request.form.get('motivo') or '').strip()
    if not senha or not bcrypt.check_password_hash(current_user.senha, senha):
        flash('Senha inválida. A emissão não foi cancelada.', 'danger')
        return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))
    if len(motivo) < 10:
        flash('Informe uma justificativa para o cancelamento com pelo menos 10 caracteres.', 'danger')
        return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))
    emissao.status = 'CANCELADA'
    emissao.cancelado_em = datetime.now().astimezone()
    emissao.cancelado_por_id = current_user.id
    emissao.motivo_cancelamento = motivo
    db.session.add(HistoricoProtocolo(
        tenant_id=current_tenant_id(), protocolo_id=protocolo.id, status=protocolo.status,
        responsavel=current_user.login, usuario_id=current_user.id, acao='EMISSAO_CANCELADA',
        observacao=f'Versão autenticada v{emissao.versao}, código {emissao.codigo_publico}, cancelada. Motivo: {motivo}'))
    db.session.commit()
    flash(f'A versão autenticada {emissao.versao} foi cancelada sem apagar o documento ou suas evidências.', 'success')
    return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))


@app.route('/protocolo/<int:protocolo_id>/retificar', methods=['GET', 'POST'])
@permission_required('edit')
def retificar_protocolo(protocolo_id):
    original = accessible_protocols_query().filter_by(id=protocolo_id).with_for_update().first_or_404()
    if original.arquivado_em:
        abort(409, description='Processos arquivados não podem ser retificados.')
    if not active_organization().emissao_eletronica_protocolista_enabled:
        abort(403, description='A emissão eletrônica não está habilitada para este cliente.')
    if not original.emissao_eletronica:
        flash('A retificação formal é utilizada para requerimentos já autenticados.', 'warning')
        return redirect(url_for('editar_protocolo', protocolo_id=original.id))
    if original.emissao_eletronica.status != 'VALIDA':
        abort(409, description='Somente uma emissão vigente pode ser retificada.')
    if request.method == 'GET':
        return render_template('criar_protocolo.html', title='Retificar protocolo',
                               legend=f'Retificar Protocolo {original.numero}',
                               protocolo=original, retificacao_de=original)

    nome = (request.form.get('nome') or '').strip()
    if not nome:
        abort(400, description='O nome do requerente é obrigatório.')
    for campo in ('matricula', 'endereco', 'municipio', 'bairro', 'cep', 'telefone', 'cpf', 'rg',
                  'cargo', 'lotacao', 'unidade_exercicio', 'tipo_requerimento', 'requer_ao', 'observacoes'):
        setattr(original, campo, request.form.get(campo))
    original.nome = nome
    original.data_solicitacao = (parse_iso_date(request.form.get('data_solicitacao'), 'Data da solicitação')
                                 or original.data_solicitacao or datetime.now().date())
    original.prazo_em = parse_iso_date(request.form.get('prazo_em'), 'Prazo')
    original.retificacao_pendente = True
    db.session.add(HistoricoProtocolo(
        tenant_id=current_tenant_id(), protocolo_id=original.id, status=original.status,
        responsavel=current_user.login, usuario_id=current_user.id, acao='RETIFICACAO_CRIADA',
        observacao='Nova versão preparada; a versão autenticada anterior permanece preservada até a autenticação desta retificação.'))
    db.session.commit()
    flash(f'Retificação do protocolo {original.numero} preparada. Confira e autentique a nova versão.', 'success')
    return redirect(url_for('detalhe_protocolo', protocolo_id=original.id))


@app.errorhandler(413)
def arquivo_grande_demais(_error):
    if request.is_json:
        return jsonify({'erro': 'O envio excede 30 MB no total. Cada anexo pode ter até 5 MB.'}), 413
    flash('O envio excede 30 MB no total. Cada anexo pode ter até 5 MB.', 'danger')
    return redirect(request.referrer or url_for('home'))

@app.post('/protocolo/<int:protocolo_id>/documento/gerar')
@permission_required('edit')
def gerar_documento_versionado(protocolo_id):
    protocolo = tenant_query(Protocolo).filter_by(id=protocolo_id).with_for_update().first_or_404()
    if protocolo.arquivado_em:
        flash('Processos arquivados não podem gerar novas versões.', 'warning')
        return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))
    if protocolo.emissao_eletronica:
        return _response_pdf_autenticado(protocolo.emissao_eletronica)
    pdf_bytes = render_protocol_pdf(protocolo)
    chave = 'documento-protocolo'
    versao = (tenant_query(Anexo).filter_by(protocolo_id=protocolo.id, documento_chave=chave)
              .with_entities(func.max(Anexo.versao)).scalar() or 0) + 1
    filename = f'protocolo_{protocolo.numero.replace("/", "-")}_v{versao}.pdf'
    storage_path, storage_backend, file_hash, stored_data = store_attachment_bytes(
        pdf_bytes, current_tenant_id(), protocolo.id, chave, versao, filename, 'application/pdf')
    documento = Anexo(
        tenant_id=current_tenant_id(), protocolo_id=protocolo.id,
        file_name=filename, storage_path=storage_path, storage_backend=storage_backend,
        file_hash=file_hash, file_size=len(pdf_bytes), mime_type='application/pdf', file_data=stored_data,
        documento_chave=chave, versao=versao, enviado_por_id=current_user.id)
    db.session.add_all([documento, HistoricoProtocolo(
        tenant_id=current_tenant_id(), protocolo_id=protocolo.id,
        status=protocolo.status, responsavel=current_user.login, usuario_id=current_user.id,
        acao='DOCUMENTO_GERADO', observacao=f'{filename} — versão {versao}.')])
    db.session.commit()
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename={filename}'
    return response

# --- Rotas de Protocolo ---

@app.route("/protocolos")
@login_required
def listar_protocolos():
    page = request.args.get('page', 1, type=int)
    query = apply_protocol_filters(accessible_protocols_query(), request.args)

    # Ordena por ano (descendente) e depois pelo número do protocolo (descendente)
    protocolos = query.order_by(
        func.substr(Protocolo.numero, 6, 4).desc(),
        func.substr(Protocolo.numero, 1, 4).desc()
    ).paginate(page=page, per_page=10)

    return render_template('protocolos.html', protocolos=protocolos, title="Todos os Protocolos",
                           pagination_args=pagination_filter_args(request.args))

def gerar_proximo_numero_protocolo():
    """Gera o próximo número de protocolo no formato NNNN/ANO."""
    now = datetime.now()
    current_year = now.year

    # A linha da organização serializa a numeração por cliente no PostgreSQL.
    Organizacao.query.filter_by(id=current_tenant_id()).with_for_update().one()
    # Busca os protocolos dentro da mesma transação protegida.
    protocolos_do_ano = tenant_query(Protocolo).filter(
        Protocolo.numero.like(f'%/{current_year}')
    ).all()

    if not protocolos_do_ano:
        # Se não houver nenhum protocolo no ano, começa do 1
        novo_sequencial = 1
    else:
        # Extrai e encontra o maior número sequencial
        maior_sequencial = 0
        for p in protocolos_do_ano:
            try:
                sequencial_atual = int(p.numero.split('/')[0])
                if sequencial_atual > maior_sequencial:
                    maior_sequencial = sequencial_atual
            except (ValueError, IndexError):
                # Ignora números de protocolo em formato inesperado
                continue
        novo_sequencial = maior_sequencial + 1

    # Formata o novo número com 4 dígitos, preenchendo com zeros à esquerda
    return f'{str(novo_sequencial).zfill(4)}/{current_year}'

@app.route("/protocolo/novo", methods=['GET', 'POST'])
@permission_required('create')
def criar_protocolo():
    if request.method == 'POST':
        # O número exibido no navegador é apenas informativo; o servidor é a autoridade.
        novo_numero = gerar_proximo_numero_protocolo()

        # Converte a data de string para objeto date
        data_solicitacao_str = request.form.get('data_solicitacao')
        data_solicitacao_obj = parse_iso_date(data_solicitacao_str, 'Data da solicitação') or datetime.now().date()
        prazo_obj = parse_iso_date(request.form.get('prazo_em'), 'Prazo')
        nome = (request.form.get('nome') or '').strip()
        if not nome:
            abort(400, description='O nome do requerente é obrigatório.')

        protocolo = Protocolo(
            tenant_id=current_tenant_id(),
            numero=novo_numero,
            nome=nome,
            matricula=request.form.get('matricula'),
            endereco=request.form.get('endereco'),
            municipio=request.form.get('municipio'),
            bairro=request.form.get('bairro'),
            cep=request.form.get('cep'),
            telefone=request.form.get('telefone'),
            cpf=request.form.get('cpf'),
            rg=request.form.get('rg'),
            cargo=request.form.get('cargo'),
            lotacao=request.form.get('lotacao'),
            unidade_exercicio=request.form.get('unidade_exercicio'),
            tipo_requerimento=request.form.get('tipo_requerimento'),
            requer_ao=request.form.get('requer_ao'),
            data_solicitacao=data_solicitacao_obj,
            prazo_em=prazo_obj,
            observacoes=request.form.get('observacoes'),
            responsavel=current_user.login,
            criado_por_id=current_user.id,
            modalidade_abertura='presencial_protocolista',
            setor_atual_id=current_user.lotacao_id,
            status='PROTOCOLO GERADO' # Status padrão como no sistema antigo
        )
        db.session.add(protocolo)
        db.session.flush()
        historico = HistoricoProtocolo(
            tenant_id=current_tenant_id(),
            protocolo_id=protocolo.id,
            status=protocolo.status,
            responsavel=protocolo.responsavel,
            usuario_id=current_user.id,
            acao='CRIACAO',
            observacao='Protocolo criado no sistema.'
        )
        db.session.add(historico)
        db.session.commit()

        flash(f'Protocolo {novo_numero} criado com sucesso!', 'success')
        return redirect(url_for('listar_protocolos'))

    # Para requisições GET, apenas renderiza o template.
    # Os dados serão preenchidos via JavaScript.
    return render_template('criar_protocolo.html', title='Novo Protocolo', legend='Novo Protocolo')

@app.route("/protocolo/<int:protocolo_id>")
@login_required
def detalhe_protocolo(protocolo_id):
    protocolo = accessible_protocol_or_404(protocolo_id)
    anexo_form = AnexoForm()
    lotacoes = tenant_query(Lotacao).filter_by(ativo=True).order_by(Lotacao.nome).all()
    usuarios_destino = tenant_query(Usuario).filter_by(status='ativo').filter(
        Usuario.lotacao_id.isnot(None)).order_by(Usuario.nome).all()
    pendente = tenant_query(Movimentacao).filter_by(protocolo_id=protocolo.id, recebido_em=None).order_by(Movimentacao.id.desc()).first()
    pode_receber = bool(pendente and (
        current_user.tipo == 'admin' or
        (current_user.lotacao_id == pendente.setor_destino_id and
         (not pendente.destinatario_usuario_id or pendente.destinatario_usuario_id == current_user.id))))
    pode_encaminhar = can_operate_protocol(protocolo) and not pendente
    documentos = {}
    for anexo in sorted(protocolo.anexos, key=lambda item: (item.versao, item.id)):
        # Os anexos anteriores ao versionamento tinham todos a chave 'anexo'.
        chave = anexo.documento_chave if anexo.documento_chave != 'anexo' else f'legado-{anexo.id}'
        documentos[chave] = anexo
    return render_template('protocolo_detalhe.html', title=f"Protocolo {protocolo.numero}", protocolo=protocolo, anexo_form=anexo_form, lotacoes=lotacoes, usuarios_destino=usuarios_destino, movimentacao_pendente=pendente, pode_receber=pode_receber, pode_encaminhar=pode_encaminhar, documentos_atuais=list(documentos.values()))


@app.post('/protocolo/<int:protocolo_id>/solicitar-complemento')
@permission_required('edit')
def solicitar_complemento(protocolo_id):
    protocolo = accessible_protocol_or_404(protocolo_id)
    if protocolo.arquivado_em:
        abort(409, description='Processos arquivados não podem receber solicitações.')
    if protocolo.modalidade_abertura != 'remota_requerente' or not protocolo.requerente_servidor_id:
        flash('A complementação pelo portal está disponível para requerimentos enviados remotamente.', 'warning')
        return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))
    motivo = (request.form.get('motivo') or '').strip()
    if len(motivo) < 10:
        flash('Descreva o documento ou informação necessária com pelo menos 10 caracteres.', 'danger')
        return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))
    solicitacao = SolicitacaoComplemento(
        tenant_id=current_tenant_id(), protocolo_id=protocolo.id,
        solicitado_por_id=current_user.id, motivo=motivo, status='PENDENTE')
    db.session.add(solicitacao)
    db.session.flush()
    db.session.add(HistoricoProtocolo(
        tenant_id=current_tenant_id(), protocolo_id=protocolo.id, status=protocolo.status,
        responsavel=current_user.login, usuario_id=current_user.id,
        acao='COMPLEMENTO_SOLICITADO',
        observacao=f'Solicitação de complemento #{solicitacao.id}: {motivo}'))
    db.session.commit()
    flash('Solicitação registrada. O requerente será avisado no Portal do Servidor.', 'success')
    return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))

@app.route("/protocolo/<int:protocolo_id>/editar", methods=['GET', 'POST'])
@permission_required('edit')
def editar_protocolo(protocolo_id):
    protocolo = accessible_protocol_or_404(protocolo_id)
    if protocolo.arquivado_em:
        flash('Processos arquivados são somente para consulta.', 'warning')
        return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))
    if protocolo.emissao_eletronica and not protocolo.retificacao_pendente:
        flash('O requerimento autenticado está congelado. Faça uma retificação para alterar seus dados.', 'warning')
        return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))

    if request.method == 'POST':
        campos = ('nome', 'matricula', 'endereco', 'municipio', 'bairro', 'cep', 'telefone', 'cpf', 'rg', 'cargo', 'lotacao', 'unidade_exercicio', 'tipo_requerimento', 'requer_ao', 'observacoes')
        anteriores = {campo: getattr(protocolo, campo) for campo in campos}
        prazo_anterior, data_anterior = protocolo.prazo_em, protocolo.data_solicitacao
        # Manual update from form data
        protocolo.nome = request.form.get('nome')
        protocolo.matricula = request.form.get('matricula')
        protocolo.endereco = request.form.get('endereco')
        protocolo.municipio = request.form.get('municipio')
        protocolo.bairro = request.form.get('bairro')
        protocolo.cep = request.form.get('cep')
        protocolo.telefone = request.form.get('telefone')
        protocolo.cpf = request.form.get('cpf')
        protocolo.rg = request.form.get('rg')
        protocolo.cargo = request.form.get('cargo')
        protocolo.lotacao = request.form.get('lotacao')
        protocolo.unidade_exercicio = request.form.get('unidade_exercicio')
        protocolo.tipo_requerimento = request.form.get('tipo_requerimento')
        protocolo.requer_ao = request.form.get('requer_ao')

        data_solicitacao_str = request.form.get('data_solicitacao')
        if data_solicitacao_str:
            protocolo.data_solicitacao = parse_iso_date(data_solicitacao_str, 'Data da solicitação')

        protocolo.observacoes = request.form.get('observacoes')
        protocolo.prazo_em = parse_iso_date(request.form.get('prazo_em'), 'Prazo')
        alteracoes = [f'{campo}: {anteriores[campo] or "(vazio)"} → {getattr(protocolo, campo) or "(vazio)"}' for campo in campos if anteriores[campo] != getattr(protocolo, campo)]
        if data_anterior != protocolo.data_solicitacao:
            alteracoes.append(f'data_solicitacao: {data_anterior or "(vazio)"} → {protocolo.data_solicitacao or "(vazio)"}')
        if prazo_anterior != protocolo.prazo_em:
            alteracoes.append(f'prazo: {prazo_anterior or "(vazio)"} → {protocolo.prazo_em or "(vazio)"}')

        historico = HistoricoProtocolo(
            tenant_id=current_tenant_id(),
            protocolo_id=protocolo.id,
            status=protocolo.status,
            responsavel=current_user.login,
            usuario_id=current_user.id,
            acao='EDICAO',
            observacao='; '.join(alteracoes) if alteracoes else 'Formulário salvo sem alteração de dados.'
        )
        db.session.add(historico)
        db.session.commit()

        flash('Protocolo atualizado com sucesso!', 'success')
        return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))

    # For GET request, pass the protocol object to the template
    return render_template('criar_protocolo.html',
                           title='Editar Protocolo',
                           legend=f'Editar Protocolo {protocolo.numero}',
                           protocolo=protocolo)

@app.route("/protocolo/<int:protocolo_id>/deletar", methods=['POST'])
@permission_required('delete')
def deletar_protocolo(protocolo_id):
    protocolo = accessible_protocol_or_404(protocolo_id)
    flash('A exclusão permanente está desativada para preservar o histórico. Utilize o arquivamento eletrônico.', 'warning')
    return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))

# --- Rotas de Anexos ---

@app.route("/protocolo/<int:protocolo_id>/anexo/novo", methods=['POST'])
@permission_required('edit')
def adicionar_anexo(protocolo_id):
    # Serializa versões do mesmo processo no PostgreSQL, inclusive uploads simultâneos.
    protocolo = tenant_query(Protocolo).filter_by(id=protocolo_id).with_for_update().first_or_404()
    if protocolo.arquivado_em:
        flash('Processos arquivados não podem receber anexos ou novas versões.', 'warning')
        return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))
    if protocolo.emissao_eletronica and not protocolo.retificacao_pendente:
        flash('Os anexos que integram a emissão autenticada estão congelados. Faça uma retificação para complementar o pedido.', 'warning')
        return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))
    form = AnexoForm()
    if form.validate_on_submit():
        file = form.anexo.data
        filename = secure_filename(file.filename)
        file_data = file.read(5 * 1024 * 1024 + 1)
        if not filename or not file_data or len(file_data) > 5 * 1024 * 1024:
            flash('Envie um arquivo não vazio, com nome válido e até 5 MB.', 'danger')
            return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))
        mime_type = verified_upload_mime(filename, file_data)
        if not mime_type:
            flash('O conteúdo do arquivo não corresponde a um tipo permitido.', 'danger')
            return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))
        chave = secrets.token_urlsafe(24)
        versao = 1
        documento_id = request.form.get('documento_id', '').strip()
        if documento_id:
            if not documento_id.isdecimal():
                return 'Documento inválido.', 400
            anterior = tenant_query(Anexo).filter_by(id=int(documento_id), protocolo_id=protocolo.id).first_or_404()
            if anterior.documento_chave == 'anexo':
                anterior.documento_chave = chave
                db.session.flush()
            else:
                chave = anterior.documento_chave
            versao = (tenant_query(Anexo).filter_by(protocolo_id=protocolo.id, documento_chave=chave)
                      .with_entities(func.max(Anexo.versao)).scalar() or 0) + 1

        storage_path, storage_backend, file_hash, stored_data = store_attachment_bytes(
            file_data, current_tenant_id(), protocolo.id, chave, versao, filename, mime_type)
        novo_anexo = Anexo(
            tenant_id=current_tenant_id(),
            protocolo_id=protocolo.id,
            file_name=filename,
            storage_path=storage_path,
            storage_backend=storage_backend,
            file_hash=file_hash,
            file_size=len(file_data),
            mime_type=mime_type,
            file_data=stored_data,
            enviado_por_id=current_user.id,
            documento_chave=chave,
            versao=versao,
        )
        db.session.add(novo_anexo)
        db.session.add(HistoricoProtocolo(
            tenant_id=current_tenant_id(), protocolo_id=protocolo.id,
            status=protocolo.status, responsavel=current_user.login, usuario_id=current_user.id,
            acao='NOVA_VERSAO_DOCUMENTO' if versao > 1 else 'ANEXO_ADICIONADO',
            observacao=f'{filename} — versão {versao}. Documento {chave}.',
        ))
        db.session.commit()
        flash(f'Documento enviado com sucesso! Versão {versao}; versões anteriores preservadas.', 'success')
    else:
        # Pega o primeiro erro de validação para exibir
        error_messages = [error for field, errors in form.errors.items() for error in errors]
        flash(f'Erro no envio do anexo: {error_messages[0]}', 'danger')

    return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo_id))

@app.route("/anexo/<int:anexo_id>/download")
@login_required
def baixar_anexo(anexo_id):
    anexo = tenant_get_or_404(Anexo, anexo_id)
    accessible_protocol_or_404(anexo.protocolo_id)
    try:
        file_data = read_attachment_bytes(anexo)
    except Exception:
        app.logger.exception('Falha ao recuperar ou validar anexo %s.', anexo.id)
        return 'O arquivo está temporariamente indisponível.', 503
    return send_file(
        io.BytesIO(file_data),
        mimetype=anexo.mime_type,
        as_attachment=True,
        download_name=anexo.file_name
    )

@app.route("/anexo/<int:anexo_id>/deletar", methods=['POST'])
@permission_required('delete')
def deletar_anexo(anexo_id):
    anexo = tenant_get_or_404(Anexo, anexo_id)
    protocolo_id = anexo.protocolo_id
    flash('As versões são preservadas para auditoria. Envie uma nova versão para corrigir o documento.', 'warning')
    return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo_id))

@app.route("/protocolos/atualizar", methods=['POST'])
@permission_required('route')
def atualizar_protocolo_status():
    data = request.get_json()
    protocolo_id = data.get('protocoloId')
    novo_status = data.get('novoStatus')
    novo_responsavel = data.get('novoResponsavel') # Pode ser nulo
    observacao = data.get('observacao')

    if not protocolo_id or novo_status not in PROTOCOL_STATUSES or novo_status in ('EM TRAMITAÇÃO', 'ARQUIVADO'):
        return jsonify({'sucesso': False, 'mensagem': 'Dados insuficientes.'}), 400

    protocolo = accessible_protocol_or_404(protocolo_id)
    if not can_operate_protocol(protocolo):
        return jsonify({'sucesso': False, 'mensagem': 'O processo não está sob responsabilidade do seu setor.'}), 403
    if protocolo.arquivado_em:
        return jsonify({'sucesso': False, 'mensagem': 'Processo arquivado é somente para consulta.'}), 409

    # Atualiza o protocolo
    protocolo.status = novo_status
    if novo_responsavel:
        protocolo.responsavel = novo_responsavel

    # Adiciona registro ao histórico
    historico = HistoricoProtocolo(
        tenant_id=current_tenant_id(),
        protocolo_id=protocolo.id,
        status=novo_status,
        responsavel=current_user.login, # Quem fez a ação
        usuario_id=current_user.id,
        acao='ALTERACAO_STATUS',
        observacao=observacao
    )
    db.session.add(historico)

    try:
        db.session.commit()
        return jsonify({'sucesso': True, 'mensagem': 'Protocolo atualizado com sucesso.'})
    except Exception as e:
        db.session.rollback()
        app.logger.exception('Falha ao atualizar o status do protocolo.')
        return jsonify({'sucesso': False, 'mensagem': 'Não foi possível concluir a operação.'}), 500

@app.post('/protocolo/<int:protocolo_id>/tramitar')
@permission_required('route')
def tramitar_protocolo(protocolo_id):
    protocolo = accessible_protocol_or_404(protocolo_id)
    if not can_operate_protocol(protocolo):
        abort(403)
    setor_destino = tenant_get_or_404(Lotacao, request.form.get('setor_destino_id', type=int))
    destinatario_id = request.form.get('destinatario_usuario_id', type=int)
    destinatario = None
    if destinatario_id:
        destinatario = tenant_query(Usuario).filter_by(
            id=destinatario_id, lotacao_id=setor_destino.id, status='ativo').first_or_404()
    if protocolo.arquivado_em:
        flash('Um processo arquivado não pode ser tramitado.', 'danger')
        return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))
    if tenant_query(Movimentacao).filter_by(protocolo_id=protocolo.id, recebido_em=None).first():
        flash('Já existe uma tramitação aguardando recebimento.', 'danger')
        return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))

    movimento = Movimentacao(
        tenant_id=current_tenant_id(),
        protocolo_id=protocolo.id,
        setor_origem_id=protocolo.setor_atual_id,
        setor_destino_id=setor_destino.id,
        destinatario_usuario_id=destinatario.id if destinatario else None,
        enviado_por_id=current_user.id,
        observacao=request.form.get('observacao'),
    )
    protocolo.status = 'EM TRAMITAÇÃO'
    db.session.add_all([movimento, HistoricoProtocolo(
        tenant_id=current_tenant_id(),
        protocolo_id=protocolo.id,
        status=protocolo.status,
        responsavel=current_user.login,
        usuario_id=current_user.id,
        acao='TRAMITACAO',
        observacao=(f'Encaminhado para {setor_destino.nome}' +
                    (f', aos cuidados de {destinatario.nome}' if destinatario else ', disponível a todos do setor') +
                    f'. {movimento.observacao or ""}').strip(),
    )])
    db.session.commit()
    flash(f'Processo encaminhado para {setor_destino.nome}' +
          (f', aos cuidados de {destinatario.nome}.' if destinatario else ', disponível a todos do setor.'), 'success')
    return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))

@app.post('/protocolo/<int:protocolo_id>/receber')
@permission_required('route')
def receber_protocolo(protocolo_id):
    protocolo = accessible_protocol_or_404(protocolo_id)
    movimento = tenant_query(Movimentacao).filter_by(protocolo_id=protocolo.id, recebido_em=None).order_by(Movimentacao.id.desc()).first_or_404()
    if current_user.tipo != 'admin' and (
            current_user.lotacao_id != movimento.setor_destino_id or
            (movimento.destinatario_usuario_id and movimento.destinatario_usuario_id != current_user.id)):
        flash('O recebimento deve ser feito pelo setor destinatário.', 'danger')
        return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))
    movimento.recebido_por_id = current_user.id
    movimento.recebido_em = datetime.utcnow()
    protocolo.setor_atual_id = movimento.setor_destino_id
    protocolo.responsavel = current_user.login
    protocolo.status = 'EM ANÁLISE'
    db.session.add(HistoricoProtocolo(
        tenant_id=current_tenant_id(), protocolo_id=protocolo.id,
        status=protocolo.status, responsavel=current_user.login,
        usuario_id=current_user.id, acao='RECEBIMENTO',
        observacao=f'Recebido pelo setor {movimento.setor_destino.nome}.',
    ))
    db.session.commit()
    flash('Processo recebido com sucesso.', 'success')
    return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))

@app.post('/protocolo/<int:protocolo_id>/arquivar')
@permission_required('archive')
def arquivar_protocolo(protocolo_id):
    protocolo = accessible_protocol_or_404(protocolo_id)
    pendente = tenant_query(Movimentacao).filter_by(protocolo_id=protocolo.id, recebido_em=None).first()
    if pendente:
        flash('Receba ou regularize a tramitação pendente antes de arquivar.', 'warning')
        return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))
    if protocolo.arquivado_em:
        flash('O processo já está arquivado.', 'info')
        return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))
    protocolo.arquivado_em = datetime.utcnow()
    protocolo.status = 'ARQUIVADO'
    db.session.add(HistoricoProtocolo(
        tenant_id=current_tenant_id(), protocolo_id=protocolo.id,
        status=protocolo.status, responsavel=current_user.login,
        usuario_id=current_user.id, acao='ARQUIVAMENTO',
        observacao=request.form.get('observacao') or 'Processo arquivado eletronicamente.',
    ))
    db.session.commit()
    flash('Processo arquivado eletronicamente.', 'success')
    return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))

# --- Rota de Backup ---

@app.route('/protocolos/backup/excel')
@permission_required('reports')
def backup_excel():
    """Gera um arquivo Excel com todos os protocolos, aplicando os filtros ativos."""
    query = apply_protocol_filters(accessible_protocols_query(), request.args)

    protocolos = query.order_by(Protocolo.id.asc()).all()

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Backup Protocolos'

    headers = [
        'Número', 'Matrícula', 'Nome', 'Endereço', 'Município', 'Bairro', 'CEP',
        'Telefone', 'CPF', 'RG', 'Cargo', 'Lotação', 'Unidade', 'Tipo de Requerimento',
        'Requer ao', 'Data Solicitação', 'Prazo', 'Observações', 'Status', 'Responsável'
    ]
    sheet.append(headers)

    for p in protocolos:
        row = [
            p.numero, p.matricula, p.nome, p.endereco, p.municipio, p.bairro, p.cep,
            p.telefone, p.cpf, p.rg, p.cargo, p.lotacao, p.unidade_exercicio,
            p.tipo_requerimento, p.requer_ao,
            p.data_solicitacao.strftime('%Y-%m-%d') if p.data_solicitacao else '',
            p.prazo_em.strftime('%Y-%m-%d') if p.prazo_em else '',
            p.observacoes, p.status, p.responsavel
        ]
        sheet.append(row)
        for cell in sheet[sheet.max_row]:
            if isinstance(cell.value, str):
                cell.data_type = 's'

    virtual_workbook = io.BytesIO()
    workbook.save(virtual_workbook)
    virtual_workbook.seek(0)

    return send_file(
        virtual_workbook,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='backup_protocolos.xlsx'
    )

# --- API Routes for Dynamic Data ---

@app.route('/api/usuarios')
@permission_required('route')
def get_usuarios():
    """Retorna uma lista de usuários ativos para preencher selects."""
    try:
        usuarios = tenant_query(Usuario).filter_by(status='ativo').all()
        # Retornando apenas os campos necessários para evitar expor dados sensíveis
        usuarios_list = [{'id': u.id, 'login': u.login, 'nome': u.nome} for u in usuarios]
        return jsonify(usuarios_list)
    except Exception as e:
        app.logger.exception('Falha ao listar usuários da organização.')
        return jsonify({'error': 'Não foi possível obter os usuários.'}), 500

@app.route('/api/servidor/<string:matricula>')
@permission_required('create')
def get_servidor(matricula):
    servidor = tenant_query(Servidor).filter_by(matricula=matricula).first()
    if servidor:
        return jsonify({
            'matricula': servidor.matricula,
            'nome': servidor.nome,
            'lotacao': servidor.lotacao,
            'cargo': servidor.cargo,
            'unidade_de_exercicio': servidor.unidade_de_exercicio
        })
    return jsonify({'error': 'Servidor não encontrado'}), 404

@app.route('/api/servidores/search')
@permission_required('create')
def search_servidores():
    query_nome = request.args.get('nome', '')
    if len(query_nome) < 3:
        return jsonify({'error': 'A busca requer ao menos 3 caracteres'}), 400

    servidores = tenant_query(Servidor).filter(Servidor.nome.ilike(f'%{query_nome}%')).limit(10).all()
    return jsonify([{
        'matricula': s.matricula,
        'nome': s.nome,
        'lotacao': s.lotacao,
        'cargo': s.cargo,
        'unidade_de_exercicio': s.unidade_de_exercicio
    } for s in servidores])

@app.route('/api/lotacoes')
@login_required
def get_lotacoes():
    lotacoes = tenant_query(Lotacao).filter_by(ativo=True).order_by(Lotacao.nome).all()
    return jsonify([l.nome for l in lotacoes])

@app.route('/api/tipos_requerimento')
@login_required
def get_tipos_requerimento():
    tipos = tenant_query(TipoRequerimento).filter_by(ativo=True).order_by(TipoRequerimento.nome).all()
    return jsonify([t.nome for t in tipos])

@app.route('/api/bairros')
@login_required
def get_bairros():
    """Retorna somente bairros já utilizados pela organização autenticada."""
    bairros = tenant_query(Protocolo).with_entities(Protocolo.bairro).filter(
        Protocolo.bairro.is_not(None), Protocolo.bairro != ''
    ).distinct().order_by(Protocolo.bairro).all()
    nomes = [bairro for bairro, in bairros if bairro.strip()]
    if not any(nome.casefold() == 'outro' for nome in nomes):
        nomes.append('Outro')
    return jsonify(nomes)

@app.route('/protocolos/ultimoNumero/<int:ano>')
@permission_required('create')
def get_ultimo_numero(ano):
    """Obtém o último número de protocolo para um determinado ano."""
    protocolos_do_ano = tenant_query(Protocolo).filter(
        Protocolo.numero.like(f'%/{ano}')
    ).all()

    if not protocolos_do_ano:
        maior_sequencial = 0
    else:
        maior_sequencial = 0
        for p in protocolos_do_ano:
            try:
                sequencial_atual = int(p.numero.split('/')[0])
                if sequencial_atual > maior_sequencial:
                    maior_sequencial = sequencial_atual
            except (ValueError, IndexError):
                continue

    return jsonify({'ultimo': maior_sequencial})

@app.route('/api/protocolo/<int:protocolo_id>')
@login_required
def get_protocolo_api(protocolo_id):
    protocolo = accessible_protocol_or_404(protocolo_id)
    return jsonify({
        'id': protocolo.id,
        'numero': protocolo.numero,
        'nome': protocolo.nome,
        'matricula': protocolo.matricula,
        'endereco': protocolo.endereco,
        'municipio': protocolo.municipio,
        'bairro': protocolo.bairro,
        'cep': protocolo.cep,
        'telefone': protocolo.telefone,
        'cpf': protocolo.cpf,
        'rg': protocolo.rg,
        'cargo': protocolo.cargo,
        'lotacao': protocolo.lotacao,
        'unidade_exercicio': protocolo.unidade_exercicio,
        'tipo_requerimento': protocolo.tipo_requerimento,
        'requer_ao': protocolo.requer_ao,
        'data_solicitacao': protocolo.data_solicitacao.isoformat() if protocolo.data_solicitacao else None,
        'observacoes': protocolo.observacoes,
        'status': protocolo.status,
        'responsavel': protocolo.responsavel,
        'localizacao_atual': protocol_location(protocolo),
        'consulta_token': protocolo.consulta_token,
    })

@app.route('/protocolos/dashboard-stats')
@login_required
def dashboard_stats():
    try:
        # --- Filter Parsing ---
        data_inicio_str = request.args.get('dataInicio')
        data_fim_str = request.args.get('dataFim')
        status = request.args.get('status')
        tipo = request.args.get('tipo')
        lotacao = request.args.get('lotacao')
        evolucao_periodo = request.args.get('evolucaoPeriodo', '30d')
        evolucao_agrupamento = request.args.get('evolucaoAgrupamento', 'day')

        # --- Base Query Construction ---
        base_query = accessible_protocols_query()
        if status:
            base_query = base_query.filter(Protocolo.status == status)
        if tipo:
            base_query = base_query.filter(Protocolo.tipo_requerimento == tipo)
        if lotacao:
            base_query = base_query.join(Lotacao, Protocolo.setor_atual_id == Lotacao.id).filter(
                Lotacao.tenant_id == current_tenant_id(), Lotacao.nome == lotacao)

        # --- Period-Filtered Query ---
        period_query = base_query
        if data_inicio_str:
            period_query = period_query.filter(Protocolo.data_solicitacao >= datetime.strptime(data_inicio_str, '%Y-%m-%d').date())
        if data_fim_str:
            period_query = period_query.filter(Protocolo.data_solicitacao <= datetime.strptime(data_fim_str, '%Y-%m-%d').date())

        # --- Novos no Período (Card) ---
        novos_query = base_query.filter(Protocolo.data_solicitacao != None)
        if data_inicio_str:
             novos_query = novos_query.filter(Protocolo.data_solicitacao >= datetime.strptime(data_inicio_str, '%Y-%m-%d').date())
        else: # Default to last 7 days if no start date
             novos_query = novos_query.filter(Protocolo.data_solicitacao >= (datetime.now().date() - timedelta(days=7)))
        if data_fim_str:
             novos_query = novos_query.filter(Protocolo.data_solicitacao <= datetime.strptime(data_fim_str, '%Y-%m-%d').date())

        novos_no_periodo = novos_query.count()

        # --- Prazos vencidos (Card) ---
        encerrados = ['FINALIZADO', 'CONCLUÍDO', 'ARQUIVADO']
        pendentes_antigos = base_query.filter(
            Protocolo.prazo_em != None, Protocolo.prazo_em < datetime.now().date(),
            ~Protocolo.status.in_(encerrados)).count()

        hoje = datetime.now().date()
        vencem_proximos_7 = base_query.filter(
            Protocolo.prazo_em != None,
            Protocolo.prazo_em >= hoje,
            Protocolo.prazo_em <= hoje + timedelta(days=7),
            ~Protocolo.status.in_(encerrados)).count()
        sem_prazo = base_query.filter(
            Protocolo.prazo_em == None,
            ~Protocolo.status.in_(encerrados)).count()

        # --- Finalizados no Período (Card) ---
        total_finalizados = period_query.filter(Protocolo.status.in_(['FINALIZADO', 'CONCLUÍDO'])).count()

        # --- Top 5 Tipos (Bar Chart) ---
        top_tipos = period_query.with_entities(
            Protocolo.tipo_requerimento,
            func.count(Protocolo.id).label('total')
        ).filter(Protocolo.tipo_requerimento != None, Protocolo.tipo_requerimento != '').group_by(Protocolo.tipo_requerimento).order_by(func.count(Protocolo.id).desc()).limit(5).all()

        # --- Data for Pie Chart (Status or Tipo) ---
        todos_tipos = period_query.with_entities(
            Protocolo.tipo_requerimento,
            func.count(Protocolo.id).label('total')
        ).filter(Protocolo.tipo_requerimento != None, Protocolo.tipo_requerimento != '').group_by(Protocolo.tipo_requerimento).order_by(func.count(Protocolo.id).desc()).all()

        status_protocolos = period_query.with_entities(
            Protocolo.status,
            func.count(Protocolo.id).label('total')
        ).filter(Protocolo.status != None, Protocolo.status != '').group_by(Protocolo.status).all()

        setor_query = period_query if lotacao else period_query.outerjoin(
            Lotacao, Protocolo.setor_atual_id == Lotacao.id)
        setor_protocolos = setor_query.with_entities(
            func.coalesce(Lotacao.nome, 'Não definido').label('setor'),
            func.count(Protocolo.id).label('total')
        ).group_by(func.coalesce(Lotacao.nome, 'Não definido')).order_by(func.count(Protocolo.id).desc()).all()

        # --- Evolução (Line Chart) ---
        evolucao_query = base_query.filter(Protocolo.data_solicitacao != None)
        today = datetime.now().date()
        is_sqlite = db.session.get_bind().dialect.name == 'sqlite'
        if evolucao_periodo == '7d':
            evolucao_query = evolucao_query.filter(Protocolo.data_solicitacao >= (today - timedelta(days=7)))
        elif evolucao_periodo == 'month':
            if is_sqlite:
                evolucao_query = evolucao_query.filter(func.strftime('%Y-%m', Protocolo.data_solicitacao) == today.strftime('%Y-%m'))
            else:
                evolucao_query = evolucao_query.filter(func.date_trunc('month', Protocolo.data_solicitacao) == func.date_trunc('month', today))
        elif evolucao_periodo == 'all':
             evolucao_query = evolucao_query.filter(Protocolo.data_solicitacao >= '2025-01-01')
        else: # 30d default
            evolucao_query = evolucao_query.filter(Protocolo.data_solicitacao >= (today - timedelta(days=30)))

        if is_sqlite:
            group_by_logic = func.strftime('%Y-%m-01', Protocolo.data_solicitacao) if evolucao_agrupamento == 'month' else func.strftime('%Y-%m-%d', Protocolo.data_solicitacao)
        else:
            group_by_logic = func.date_trunc('month', Protocolo.data_solicitacao) if evolucao_agrupamento == 'month' else cast(Protocolo.data_solicitacao, Date)

        evolucao_protocolos = evolucao_query.with_entities(
            group_by_logic.label('intervalo'),
            func.count(Protocolo.id).label('total')
        ).group_by('intervalo').order_by('intervalo').all()

        # --- JSON Response Assembly ---
        stats = {
            'novosNoPeriodo': novos_no_periodo,
            'pendentesAntigos': pendentes_antigos or 0,
            'vencemProximos7': vencem_proximos_7 or 0,
            'semPrazo': sem_prazo or 0,
            'totalFinalizados': total_finalizados,
            'topTipos': [{'tipo_requerimento': r.tipo_requerimento, 'total': r.total} for r in top_tipos],
            'todosTipos': [{'tipo_requerimento': r.tipo_requerimento, 'total': r.total} for r in todos_tipos],
            'statusProtocolos': [{'status': r.status, 'total': r.total} for r in status_protocolos],
            'setorProtocolos': [{'setor': r.setor, 'total': r.total} for r in setor_protocolos],
            'evolucaoProtocolos': [{'intervalo': r.intervalo.isoformat() if hasattr(r.intervalo, 'isoformat') else str(r.intervalo), 'total': r.total} for r in evolucao_protocolos if r.intervalo is not None]
        }
        return jsonify(stats)

    except Exception as e:
        import traceback
        app.logger.error(f"ERROR in dashboard_stats: {e}\n{traceback.format_exc()}")
        return jsonify({'error': 'Não foi possível carregar os dados do dashboard.'}), 500

if __name__ == '__main__':
    # The port must be available. Railway provides the PORT env var.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)



