import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv

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

# --- Extensions Initialization ---
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)

# --- Flask-Login Configuration ---
# 'login' is the function name of the route for the login page
login_manager.login_view = 'login'
# 'info' is a bootstrap class for message flashing
login_manager.login_message_category = 'info'

# --- Imports for Routes and Models ---
from flask import render_template, url_for, flash, redirect, request
from flask_login import login_user, current_user, logout_user, login_required
from flask import send_file, Response, jsonify, make_response
from werkzeug.utils import secure_filename
import io
import hmac
import hashlib
from openpyxl import Workbook
from sqlalchemy import func, cast, Date
from datetime import datetime, timedelta
from forms import LoginForm, RegistrationForm, ProtocoloForm, AnexoForm, AdminUserCreationForm, AdminListItemForm, ConsultaPublicaForm
from models import Organizacao, Usuario, Protocolo, HistoricoProtocolo, Movimentacao, ConsultaPublicaTentativa, Anexo, Lotacao, TipoRequerimento, Servidor, db
from werkzeug.middleware.proxy_fix import ProxyFix

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

def tenant_query(model):
    """Consulta obrigatoriamente limitada à organização autenticada."""
    return model.query.filter(model.tenant_id == current_user.tenant_id)

def tenant_get_or_404(model, object_id):
    return tenant_query(model).filter(model.id == object_id).first_or_404()

ROLE_PERMISSIONS = {
    'admin': {'view', 'create', 'edit', 'route', 'archive', 'delete', 'manage', 'reports'},
    'gestor': {'view', 'create', 'edit', 'route', 'archive', 'reports'},
    'user': {'view', 'create', 'edit', 'route'},
    'atendente': {'view', 'create', 'edit', 'route'},
    'consulta': {'view'},
}

@app.context_processor
def permission_context():
    return {'can': lambda permission: current_user.is_authenticated and permission in ROLE_PERMISSIONS.get(current_user.tipo, set())}

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
    return jsonify({'status': 'ok'})

@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
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
            matricula_armazenada, matricula_informada
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
            if not tentativa or tentativa.janela_iniciada_em < agora - janela:
                tentativa = ConsultaPublicaTentativa(
                    protocolo_id=protocolo.id, identificador_hash=fingerprint,
                    tentativas=0, janela_iniciada_em=agora
                )
                db.session.add(tentativa)
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

@app.route("/register", methods=['GET', 'POST'])
def register():
    flash('O cadastro público está desativado. Solicite acesso ao administrador da organização.', 'info')
    return redirect(url_for('login'))


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        organizacao = Organizacao.query.filter_by(slug=form.organizacao.data.strip().lower(), ativo=True).first()
        user = Usuario.query.filter_by(
            tenant_id=organizacao.id if organizacao else None,
            login=form.login.data,
            status='ativo'
        ).first()
        if user and bcrypt.check_password_hash(user.senha, form.senha.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            flash('Login bem-sucedido!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login sem sucesso. Por favor, verifique o login e a senha.', 'danger')
    return render_template('login.html', title='Login', form=form)


@app.route("/logout")
def logout():
    logout_user()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('login'))

@app.route("/meus_protocolos")
@login_required
def meus_protocolos():
    page = request.args.get('page', 1, type=int)
    protocolos = tenant_query(Protocolo).filter_by(responsavel=current_user.login)\
        .order_by(Protocolo.id.desc())\
        .paginate(page=page, per_page=10)
    return render_template('protocolos.html', protocolos=protocolos, title="Meus Protocolos")

from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.tipo != 'admin':
            flash('Acesso negado. Requer permissão de administrador.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/relatorios")
@login_required
def relatorios():
    # This route essentially does the same as listar_protocolos but renders a different template
    # to match the original app's structure.
    page = request.args.get('page', 1, type=int)
    query = tenant_query(Protocolo)
    # ... (filter logic is identical to listar_protocolos) ...
    if request.args.get('numero'):
        query = query.filter(Protocolo.numero.ilike(f"%{request.args.get('numero')}%"))
    if request.args.get('nome'):
        query = query.filter(Protocolo.nome.ilike(f"%{request.args.get('nome')}%"))
    if request.args.get('status'):
        query = query.filter(Protocolo.status == request.args.get('status'))
    # Add other filters as needed
    protocolos = query.order_by(Protocolo.id.desc()).paginate(page=page, per_page=10)
    return render_template('relatorios.html', protocolos=protocolos, title="Relatórios")

# --- Rotas de Configuração (Admin) ---

@app.route("/configuracoes", methods=['GET', 'POST'])
@login_required
@admin_required
def configuracoes():
    user_form = AdminUserCreationForm()
    lotacao_form = AdminListItemForm()
    tipo_form = AdminListItemForm()

    if user_form.validate_on_submit() and user_form.submit.data:
        # Lógica de criação de usuário movida para uma rota de API dedicada
        pass

    lotacoes = tenant_query(Lotacao).all()
    user_form.lotacao_id.choices = [(0, 'Sem setor definido')] + [(item.id, item.nome) for item in lotacoes if item.ativo]
    users = tenant_query(Usuario).all()
    tipos = tenant_query(TipoRequerimento).all()

    return render_template('configuracoes.html', title="Configurações",
                           users=users, lotacoes=lotacoes, tipos=tipos,
                           user_form=user_form, lotacao_form=lotacao_form, tipo_form=tipo_form)

@app.route("/admin/usuarios/novo", methods=['POST'])
@login_required
@admin_required
def admin_create_user():
    form = AdminUserCreationForm()
    lotacoes = tenant_query(Lotacao).filter_by(ativo=True).order_by(Lotacao.nome).all()
    form.lotacao_id.choices = [(0, 'Sem setor definido')] + [(item.id, item.nome) for item in lotacoes]
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.senha.data).decode('utf-8')
        user = Usuario(
            tenant_id=current_user.tenant_id,
            nome_completo=form.nome_completo.data,
            login=form.login.data,
            email=form.email.data,
            senha=hashed_password,
            nome=form.nome_completo.data.split(' ')[0],
            tipo=form.tipo.data,
            status='ativo',
            lotacao_id=form.lotacao_id.data or None,
        )
        db.session.add(user)
        db.session.commit()
        flash('Usuário criado com sucesso!', 'success')
    else:
        flash('Erro ao criar usuário. Verifique os dados.', 'danger')
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
            new_item = Model(tenant_id=current_user.tenant_id, nome=form.nome.data, ativo=True)
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

@app.route('/protocolo/<int:protocolo_id>/pdf')
@login_required
def gerar_pdf_protocolo(protocolo_id):
    from weasyprint import HTML

    protocolo = tenant_get_or_404(Protocolo, protocolo_id)

    # Renderiza um template HTML com os dados do protocolo
    # Este template é feito especificamente para ser convertido em PDF
    rendered_html = render_template('pdf_template.html', protocolo=protocolo)

    # Gera o PDF a partir do HTML renderizado
    pdf_bytes = HTML(string=rendered_html, base_url=request.base_url).write_pdf()

    # Cria a resposta HTTP com o PDF
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=protocolo_{protocolo.numero.replace("/", "-")}.pdf'

    return response

# --- Rotas de Protocolo ---

@app.route("/protocolos")
@login_required
def listar_protocolos():
    page = request.args.get('page', 1, type=int)
    query = tenant_query(Protocolo)

    # Get filter args
    numero = request.args.get('numero')
    nome = request.args.get('nome')
    status = request.args.get('status')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    tipo = request.args.get('tipo')

    # Apply filters
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

    # Ordena por ano (descendente) e depois pelo número do protocolo (descendente)
    protocolos = query.order_by(
        func.substr(Protocolo.numero, 6, 4).desc(),
        func.substr(Protocolo.numero, 1, 4).desc()
    ).paginate(page=page, per_page=10)

    return render_template('protocolos.html', protocolos=protocolos, title="Todos os Protocolos")

def gerar_proximo_numero_protocolo():
    """Gera o próximo número de protocolo no formato NNNN/ANO."""
    now = datetime.now()
    current_year = now.year

    # Busca todos os protocolos do ano corrente para encontrar o maior sequencial
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
        # Dados são pegos diretamente do 'name' dos inputs do formulário
        novo_numero = request.form.get('numero') or gerar_proximo_numero_protocolo()

        # Converte a data de string para objeto date
        data_solicitacao_str = request.form.get('data_solicitacao')
        data_solicitacao_obj = datetime.strptime(data_solicitacao_str, '%Y-%m-%d').date() if data_solicitacao_str else datetime.now().date()

        protocolo = Protocolo(
            tenant_id=current_user.tenant_id,
            numero=novo_numero,
            nome=request.form.get('nome'),
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
            prazo_em=datetime.strptime(request.form.get('prazo_em'), '%Y-%m-%d').date() if request.form.get('prazo_em') else None,
            observacoes=request.form.get('observacoes'),
            responsavel=current_user.login,
            criado_por_id=current_user.id,
            setor_atual_id=current_user.lotacao_id,
            status='PROTOCOLO GERADO' # Status padrão como no sistema antigo
        )
        db.session.add(protocolo)
        db.session.commit()

        # Adiciona o primeiro registro ao histórico
        historico = HistoricoProtocolo(
            tenant_id=current_user.tenant_id,
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
    protocolo = tenant_get_or_404(Protocolo, protocolo_id)
    anexo_form = AnexoForm()
    lotacoes = tenant_query(Lotacao).filter_by(ativo=True).order_by(Lotacao.nome).all()
    pendente = tenant_query(Movimentacao).filter_by(protocolo_id=protocolo.id, recebido_em=None).order_by(Movimentacao.id.desc()).first()
    return render_template('protocolo_detalhe.html', title=f"Protocolo {protocolo.numero}", protocolo=protocolo, anexo_form=anexo_form, lotacoes=lotacoes, movimentacao_pendente=pendente)

@app.route("/protocolo/<int:protocolo_id>/editar", methods=['GET', 'POST'])
@permission_required('edit')
def editar_protocolo(protocolo_id):
    protocolo = tenant_get_or_404(Protocolo, protocolo_id)

    if request.method == 'POST':
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
            protocolo.data_solicitacao = datetime.strptime(data_solicitacao_str, '%Y-%m-%d').date()

        protocolo.observacoes = request.form.get('observacoes')
        protocolo.prazo_em = datetime.strptime(request.form.get('prazo_em'), '%Y-%m-%d').date() if request.form.get('prazo_em') else None

        historico = HistoricoProtocolo(
            tenant_id=current_user.tenant_id,
            protocolo_id=protocolo.id,
            status=protocolo.status,
            responsavel=current_user.login,
            usuario_id=current_user.id,
            acao='EDICAO',
            observacao='Protocolo editado.'
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
    protocolo = tenant_get_or_404(Protocolo, protocolo_id)
    # Adicionar verificação de permissão aqui
    db.session.delete(protocolo)
    db.session.commit()
    flash('Protocolo excluído com sucesso.', 'success')
    return redirect(url_for('listar_protocolos'))

# --- Rotas de Anexos ---

@app.route("/protocolo/<int:protocolo_id>/anexo/novo", methods=['POST'])
@permission_required('edit')
def adicionar_anexo(protocolo_id):
    protocolo = tenant_get_or_404(Protocolo, protocolo_id)
    form = AnexoForm()
    if form.validate_on_submit():
        file = form.anexo.data
        filename = secure_filename(file.filename)
        file_data = file.read()

        novo_anexo = Anexo(
            tenant_id=current_user.tenant_id,
            protocolo_id=protocolo.id,
            file_name=filename,
            storage_path=f"{protocolo.id}/{filename}", # Manter um caminho lógico
            file_size=len(file_data),
            mime_type=file.mimetype,
            file_data=file_data,
            enviado_por_id=current_user.id,
        )
        db.session.add(novo_anexo)
        db.session.commit()
        flash('Anexo enviado com sucesso!', 'success')
    else:
        # Pega o primeiro erro de validação para exibir
        error_messages = [error for field, errors in form.errors.items() for error in errors]
        flash(f'Erro no envio do anexo: {error_messages[0]}', 'danger')

    return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo_id))

@app.route("/anexo/<int:anexo_id>/download")
@login_required
def baixar_anexo(anexo_id):
    anexo = tenant_get_or_404(Anexo, anexo_id)
    return send_file(
        io.BytesIO(anexo.file_data),
        mimetype=anexo.mime_type,
        as_attachment=True,
        download_name=anexo.file_name
    )

@app.route("/anexo/<int:anexo_id>/deletar", methods=['POST'])
@permission_required('delete')
def deletar_anexo(anexo_id):
    anexo = tenant_get_or_404(Anexo, anexo_id)
    protocolo_id = anexo.protocolo_id
    # Adicionar verificação de permissão aqui
    db.session.delete(anexo)
    db.session.commit()
    flash('Anexo excluído com sucesso.', 'success')
    return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo_id))

@app.route("/protocolos/atualizar", methods=['POST'])
@permission_required('route')
def atualizar_protocolo_status():
    data = request.get_json()
    protocolo_id = data.get('protocoloId')
    novo_status = data.get('novoStatus')
    novo_responsavel = data.get('novoResponsavel') # Pode ser nulo
    observacao = data.get('observacao')

    if not protocolo_id or not novo_status:
        return jsonify({'sucesso': False, 'mensagem': 'Dados insuficientes.'}), 400

    protocolo = tenant_get_or_404(Protocolo, protocolo_id)

    # Atualiza o protocolo
    protocolo.status = novo_status
    if novo_responsavel:
        protocolo.responsavel = novo_responsavel

    # Adiciona registro ao histórico
    historico = HistoricoProtocolo(
        tenant_id=current_user.tenant_id,
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
        return jsonify({'sucesso': False, 'mensagem': str(e)}), 500

@app.post('/protocolo/<int:protocolo_id>/tramitar')
@permission_required('route')
def tramitar_protocolo(protocolo_id):
    protocolo = tenant_get_or_404(Protocolo, protocolo_id)
    setor_destino = tenant_get_or_404(Lotacao, request.form.get('setor_destino_id', type=int))
    if protocolo.arquivado_em:
        flash('Um processo arquivado não pode ser tramitado.', 'danger')
        return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))
    if tenant_query(Movimentacao).filter_by(protocolo_id=protocolo.id, recebido_em=None).first():
        flash('Já existe uma tramitação aguardando recebimento.', 'danger')
        return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))

    movimento = Movimentacao(
        tenant_id=current_user.tenant_id,
        protocolo_id=protocolo.id,
        setor_origem_id=protocolo.setor_atual_id,
        setor_destino_id=setor_destino.id,
        enviado_por_id=current_user.id,
        observacao=request.form.get('observacao'),
    )
    protocolo.status = 'EM TRAMITAÇÃO'
    db.session.add_all([movimento, HistoricoProtocolo(
        tenant_id=current_user.tenant_id,
        protocolo_id=protocolo.id,
        status=protocolo.status,
        responsavel=current_user.login,
        usuario_id=current_user.id,
        acao='TRAMITACAO',
        observacao=f'Encaminhado para {setor_destino.nome}. {movimento.observacao or ""}'.strip(),
    )])
    db.session.commit()
    flash(f'Processo encaminhado para {setor_destino.nome}.', 'success')
    return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))

@app.post('/protocolo/<int:protocolo_id>/receber')
@permission_required('route')
def receber_protocolo(protocolo_id):
    protocolo = tenant_get_or_404(Protocolo, protocolo_id)
    movimento = tenant_query(Movimentacao).filter_by(protocolo_id=protocolo.id, recebido_em=None).order_by(Movimentacao.id.desc()).first_or_404()
    if current_user.tipo != 'admin' and current_user.lotacao_id != movimento.setor_destino_id:
        flash('O recebimento deve ser feito pelo setor destinatário.', 'danger')
        return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))
    movimento.recebido_por_id = current_user.id
    movimento.recebido_em = datetime.utcnow()
    protocolo.setor_atual_id = movimento.setor_destino_id
    protocolo.responsavel = current_user.login
    protocolo.status = 'EM ANÁLISE'
    db.session.add(HistoricoProtocolo(
        tenant_id=current_user.tenant_id, protocolo_id=protocolo.id,
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
    protocolo = tenant_get_or_404(Protocolo, protocolo_id)
    protocolo.arquivado_em = datetime.utcnow()
    protocolo.status = 'ARQUIVADO'
    db.session.add(HistoricoProtocolo(
        tenant_id=current_user.tenant_id, protocolo_id=protocolo.id,
        status=protocolo.status, responsavel=current_user.login,
        usuario_id=current_user.id, acao='ARQUIVAMENTO',
        observacao=request.form.get('observacao') or 'Processo arquivado eletronicamente.',
    ))
    db.session.commit()
    flash('Processo arquivado eletronicamente.', 'success')
    return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))

# --- Rota de Backup ---

@app.route('/protocolos/backup/excel')
@login_required
def backup_excel():
    """Gera um arquivo Excel com todos os protocolos, aplicando os filtros ativos."""
    query = tenant_query(Protocolo)

    # Re-aplica a mesma lógica de filtro da listagem
    if request.args.get('numero'):
        query = query.filter(Protocolo.numero.ilike(f"%{request.args.get('numero')}%"))
    if request.args.get('nome'):
        query = query.filter(Protocolo.nome.ilike(f"%{request.args.get('nome')}%"))
    if request.args.get('status'):
        query = query.filter(Protocolo.status == request.args.get('status'))
    if request.args.get('data_inicio'):
        query = query.filter(Protocolo.data_solicitacao >= request.args.get('data_inicio'))
    if request.args.get('data_fim'):
        query = query.filter(Protocolo.data_solicitacao <= request.args.get('data_fim'))
    if request.args.get('tipo'):
        query = query.filter(Protocolo.tipo_requerimento.ilike(f"%{request.args.get('tipo')}%"))

    protocolos = query.order_by(Protocolo.id.asc()).all()

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Backup Protocolos'

    headers = [
        'Número', 'Matrícula', 'Nome', 'Endereço', 'Município', 'Bairro', 'CEP',
        'Telefone', 'CPF', 'RG', 'Cargo', 'Lotação', 'Unidade', 'Tipo de Requerimento',
        'Requer ao', 'Data Solicitação', 'Observações', 'Status', 'Responsável'
    ]
    sheet.append(headers)

    for p in protocolos:
        row = [
            p.numero, p.matricula, p.nome, p.endereco, p.municipio, p.bairro, p.cep,
            p.telefone, p.cpf, p.rg, p.cargo, p.lotacao, p.unidade_exercicio,
            p.tipo_requerimento, p.requer_ao,
            p.data_solicitacao.strftime('%Y-%m-%d') if p.data_solicitacao else '',
            p.observacoes, p.status, p.responsavel
        ]
        sheet.append(row)

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
@login_required
def get_usuarios():
    """Retorna uma lista de usuários ativos para preencher selects."""
    try:
        usuarios = tenant_query(Usuario).filter_by(status='ativo').all()
        # Retornando apenas os campos necessários para evitar expor dados sensíveis
        usuarios_list = [{'id': u.id, 'login': u.login, 'nome': u.nome} for u in usuarios]
        return jsonify(usuarios_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/servidor/<string:matricula>')
@login_required
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
@login_required
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
    """Retorna uma lista estática de bairros."""
    bairros = [
        "Centro", "Girilândia", "Padre Assis Monteiro", "Hermógenes Henrique Girão",
        "São José", "Nossa Senhora da Conceição", "Planalto Aeroporto", "Júlia Santiago",
        "São Francisco", "Nova Morada", "Divino Espírito Santo", "Alto Tiradentes",
        "Capitão Dionísio Matos de Fontes", "Irapuan Nobre", "Dois de Agosto",
        "Cristo Rei", "Sede Rural", "Outro"
    ]
    return jsonify(sorted(bairros))

@app.route('/protocolos/ultimoNumero/<int:ano>')
@login_required
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
    protocolo = tenant_get_or_404(Protocolo, protocolo_id)
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
        base_query = tenant_query(Protocolo)
        if status:
            base_query = base_query.filter(Protocolo.status == status)
        if tipo:
            base_query = base_query.filter(Protocolo.tipo_requerimento == tipo)
        if lotacao:
            base_query = base_query.filter(Protocolo.lotacao == lotacao)

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

        # --- Pendentes Antigos (Card) ---
        pendentes_antigos = db.session.query(func.count(Protocolo.id)).filter(
            Protocolo.tenant_id == current_user.tenant_id,
            Protocolo.data_solicitacao != None,
            Protocolo.data_solicitacao <= (datetime.now().date() - timedelta(days=15)),
            ~Protocolo.status.in_(['Finalizado', 'Concluído'])
        ).scalar()

        # --- Finalizados no Período (Card) ---
        total_finalizados = period_query.filter(Protocolo.status.in_(['Finalizado', 'Concluído'])).count()

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

        # --- Evolução (Line Chart) ---
        evolucao_query = base_query.filter(Protocolo.data_solicitacao != None)
        today = datetime.now().date()
        if evolucao_periodo == '7d':
            evolucao_query = evolucao_query.filter(Protocolo.data_solicitacao >= (today - timedelta(days=7)))
        elif evolucao_periodo == 'month':
            evolucao_query = evolucao_query.filter(func.date_trunc('month', Protocolo.data_solicitacao) == func.date_trunc('month', today))
        elif evolucao_periodo == 'all':
             evolucao_query = evolucao_query.filter(Protocolo.data_solicitacao >= '2025-01-01')
        else: # 30d default
            evolucao_query = evolucao_query.filter(Protocolo.data_solicitacao >= (today - timedelta(days=30)))

        group_by_logic = func.date_trunc('month', Protocolo.data_solicitacao) if evolucao_agrupamento == 'month' else cast(Protocolo.data_solicitacao, Date)

        evolucao_protocolos = evolucao_query.with_entities(
            group_by_logic.label('intervalo'),
            func.count(Protocolo.id).label('total')
        ).group_by('intervalo').order_by('intervalo').all()

        # --- JSON Response Assembly ---
        stats = {
            'novosNoPeriodo': novos_no_periodo,
            'pendentesAntigos': pendentes_antigos or 0,
            'totalFinalizados': total_finalizados,
            'topTipos': [{'tipo_requerimento': r.tipo_requerimento, 'total': r.total} for r in top_tipos],
            'todosTipos': [{'tipo_requerimento': r.tipo_requerimento, 'total': r.total} for r in todos_tipos],
            'statusProtocolos': [{'status': r.status, 'total': r.total} for r in status_protocolos],
            'evolucaoProtocolos': [{'intervalo': r.intervalo.isoformat(), 'total': r.total} for r in evolucao_protocolos if r.intervalo is not None]
        }
        return jsonify(stats)

    except Exception as e:
        import traceback
        app.logger.error(f"ERROR in dashboard_stats: {e}\n{traceback.format_exc()}")
        return jsonify({'error': f'Ocorreu um erro no servidor ao buscar os dados do dashboard: {str(e)}'}), 500

if __name__ == '__main__':
    # The port must be available. Railway provides the PORT env var.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
