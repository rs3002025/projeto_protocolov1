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
from openpyxl import Workbook
from sqlalchemy import func, cast, Date
from datetime import datetime, timedelta
from weasyprint import HTML, CSS
from forms import LoginForm, RegistrationForm, ProtocoloForm, AnexoForm, AdminUserCreationForm, AdminListItemForm
from models import Usuario, Protocolo, HistoricoProtocolo, Anexo, Lotacao, TipoRequerimento, Servidor, db

# --- Routes ---
@app.route("/")
@app.route("/home")
@login_required
def home():
    # This page will now be rendered with the dashboard structure,
    # and the data will be fetched client-side.
    return render_template('home.html', title="Dashboard")

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.senha.data).decode('utf-8')
        # Por padrão, o primeiro usuário é admin, os outros são 'user'
        # Uma lógica mais robusta seria necessária para um sistema real
        tipo = 'admin' if Usuario.query.count() == 0 else 'user'
        user = Usuario(
            nome_completo=form.nome_completo.data,
            login=form.login.data,
            senha=hashed_password,
            nome=form.nome_completo.data.split(' ')[0], # Pega o primeiro nome
            tipo=tipo
        )
        db.session.add(user)
        db.session.commit()
        flash(f'Sua conta foi criada, {form.nome_completo.data}! Agora você pode fazer login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Registrar', form=form)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = Usuario.query.filter_by(login=form.login.data).first()
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
    protocolos = Protocolo.query.filter_by(responsavel=current_user.login)\
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
    query = Protocolo.query
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

    users = Usuario.query.all()
    lotacoes = Lotacao.query.all()
    tipos = TipoRequerimento.query.all()

    return render_template('configuracoes.html', title="Configurações",
                           users=users, lotacoes=lotacoes, tipos=tipos,
                           user_form=user_form, lotacao_form=lotacao_form, tipo_form=tipo_form)

@app.route("/admin/usuarios/novo", methods=['POST'])
@login_required
@admin_required
def admin_create_user():
    form = AdminUserCreationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.senha.data).decode('utf-8')
        user = Usuario(
            nome_completo=form.nome_completo.data,
            login=form.login.data,
            email=form.email.data,
            senha=hashed_password,
            nome=form.nome_completo.data.split(' ')[0],
            tipo=form.tipo.data,
            status='ativo'
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
            new_item = Model(nome=form.nome.data, ativo=True)
            db.session.add(new_item)
            db.session.commit()
            flash(f'{item_type.capitalize()} adicionado com sucesso!', 'success')
    else:
        flash('Erro ao adicionar item.', 'danger')
    return redirect(url_for('configuracoes'))

from flask import abort

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
        item = Model.query.get_or_404(item_id)
        item.ativo = not item.ativo
        db.session.commit()
        flash(f'Status do item alterado com sucesso!', 'success')
    return redirect(url_for('configuracoes'))

@app.route("/admin/usuarios/<int:user_id>/editar", methods=['POST'])
@login_required
@admin_required
def admin_edit_user(user_id):
    user = Usuario.query.get_or_404(user_id)
    data = request.form
    user.nome_completo = data.get('nome_completo')
    user.login = data.get('login')
    user.email = data.get('email')
    user.tipo = data.get('tipo')
    user.nome = data.get('nome_completo').split(' ')[0]
    db.session.commit()
    flash('Usuário atualizado com sucesso!', 'success')
    return redirect(url_for('configuracoes'))

@app.route("/admin/usuarios/<int:user_id>/status", methods=['POST'])
@login_required
@admin_required
def admin_toggle_user_status(user_id):
    user = Usuario.query.get_or_404(user_id)
    user.status = 'inativo' if user.status == 'ativo' else 'ativo'
    db.session.commit()
    flash('Status do usuário alterado com sucesso!', 'success')
    return redirect(url_for('configuracoes'))

@app.route("/admin/usuarios/<int:user_id>/resetar_senha", methods=['POST'])
@login_required
@admin_required
def admin_reset_password(user_id):
    user = Usuario.query.get_or_404(user_id)
    new_password = request.form.get('nova_senha')
    if not new_password or len(new_password) < 6:
        flash('Senha deve ter ao menos 6 caracteres.', 'danger')
        return redirect(url_for('configuracoes'))
    user.senha = bcrypt.generate_password_hash(new_password).decode('utf-8')
    db.session.commit()
    flash(f'Senha do usuário {user.login} foi resetada com sucesso!', 'success')
    return redirect(url_for('configuracoes'))

# --- Rotas de Protocolo ---

@app.route("/protocolos")
@login_required
def listar_protocolos():
    page = request.args.get('page', 1, type=int)
    query = Protocolo.query

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

    protocolos = query.order_by(Protocolo.id.desc()).paginate(page=page, per_page=10)

    return render_template('protocolos.html', protocolos=protocolos, title="Todos os Protocolos")

@app.route("/protocolo/novo", methods=['GET', 'POST'])
@login_required
def criar_protocolo():
    form = ProtocoloForm()
    if form.validate_on_submit():
        protocolo = Protocolo(
            numero=form.numero.data,
            nome=form.nome.data,
            matricula=form.matricula.data,
            endereco=form.endereco.data,
            municipio=form.municipio.data,
            bairro=form.bairro.data,
            cep=form.cep.data,
            telefone=form.telefone.data,
            cpf=form.cpf.data,
            rg=form.rg.data,
            cargo=form.cargo.data,
            lotacao=form.lotacao.data,
            unidade_exercicio=form.unidade_exercicio.data,
            tipo_requerimento=form.tipo_requerimento.data,
            requer_ao=form.requer_ao.data,
            data_solicitacao=form.data_solicitacao.data,
            observacoes=form.observacoes.data,
            responsavel=form.responsavel.data or current_user.login,
            status=form.status.data or 'Aberto'
        )
        db.session.add(protocolo)
        db.session.commit()

        # Adiciona o primeiro registro ao histórico
        historico = HistoricoProtocolo(
            protocolo_id=protocolo.id,
            status=protocolo.status,
            responsavel=protocolo.responsavel,
            observacao='Protocolo criado no sistema.'
        )
        db.session.add(historico)
        db.session.commit()

        flash('Protocolo criado com sucesso!', 'success')
        return redirect(url_for('listar_protocolos'))
    return render_template('criar_protocolo.html', title='Novo Protocolo', form=form, legend='Novo Protocolo')

@app.route("/protocolo/<int:protocolo_id>")
@login_required
def detalhe_protocolo(protocolo_id):
    protocolo = Protocolo.query.get_or_404(protocolo_id)
    anexo_form = AnexoForm()
    return render_template('protocolo_detalhe.html', title=f"Protocolo {protocolo.numero}", protocolo=protocolo, anexo_form=anexo_form)

@app.route("/protocolo/<int:protocolo_id>/editar", methods=['GET', 'POST'])
@login_required
def editar_protocolo(protocolo_id):
    protocolo = Protocolo.query.get_or_404(protocolo_id)
    # Adicionar verificação de permissão aqui (ex: só admin ou o responsável pode editar)
    form = ProtocoloForm(obj=protocolo) # Preenche o form com os dados do protocolo
    if form.validate_on_submit():
        # Atualiza o objeto protocolo com os dados do formulário
        form.populate_obj(protocolo)
        db.session.commit()
        flash('Protocolo atualizado com sucesso!', 'success')
        return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id))
    return render_template('criar_protocolo.html', title='Editar Protocolo', form=form, legend=f'Editar Protocolo {protocolo.numero}')

@app.route("/protocolo/<int:protocolo_id>/deletar", methods=['POST'])
@login_required
def deletar_protocolo(protocolo_id):
    protocolo = Protocolo.query.get_or_404(protocolo_id)
    # Adicionar verificação de permissão aqui
    db.session.delete(protocolo)
    db.session.commit()
    flash('Protocolo excluído com sucesso.', 'success')
    return redirect(url_for('listar_protocolos'))

# --- Rotas de Anexos ---

@app.route("/protocolo/<int:protocolo_id>/anexo/novo", methods=['POST'])
@login_required
def adicionar_anexo(protocolo_id):
    protocolo = Protocolo.query.get_or_404(protocolo_id)
    form = AnexoForm()
    if form.validate_on_submit():
        file = form.anexo.data
        filename = secure_filename(file.filename)
        file_data = file.read()

        novo_anexo = Anexo(
            protocolo_id=protocolo.id,
            file_name=filename,
            storage_path=f"{protocolo.id}/{filename}", # Manter um caminho lógico
            file_size=len(file_data),
            mime_type=file.mimetype,
            file_data=file_data
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
    anexo = Anexo.query.get_or_404(anexo_id)
    return send_file(
        io.BytesIO(anexo.file_data),
        mimetype=anexo.mime_type,
        as_attachment=True,
        download_name=anexo.file_name
    )

@app.route("/anexo/<int:anexo_id>/deletar", methods=['POST'])
@login_required
def deletar_anexo(anexo_id):
    anexo = Anexo.query.get_or_404(anexo_id)
    protocolo_id = anexo.protocolo_id
    # Adicionar verificação de permissão aqui
    db.session.delete(anexo)
    db.session.commit()
    flash('Anexo excluído com sucesso.', 'success')
    return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo_id))

@app.route("/protocolos/atualizar", methods=['POST'])
@login_required
def atualizar_protocolo_status():
    data = request.get_json()
    protocolo_id = data.get('protocoloId')
    novo_status = data.get('novoStatus')
    novo_responsavel = data.get('novoResponsavel') # Pode ser nulo
    observacao = data.get('observacao')

    if not protocolo_id or not novo_status:
        return jsonify({'sucesso': False, 'mensagem': 'Dados insuficientes.'}), 400

    protocolo = Protocolo.query.get_or_404(protocolo_id)

    # Atualiza o protocolo
    protocolo.status = novo_status
    if novo_responsavel:
        protocolo.responsavel = novo_responsavel

    # Adiciona registro ao histórico
    historico = HistoricoProtocolo(
        protocolo_id=protocolo.id,
        status=novo_status,
        responsavel=current_user.login, # Quem fez a ação
        observacao=observacao
    )
    db.session.add(historico)

    try:
        db.session.commit()
        return jsonify({'sucesso': True, 'mensagem': 'Protocolo atualizado com sucesso.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'sucesso': False, 'mensagem': str(e)}), 500

# --- Rota de Backup ---

@app.route('/protocolos/backup/excel')
@login_required
def backup_excel():
    """Gera um arquivo Excel com todos os protocolos, aplicando os filtros ativos."""
    query = Protocolo.query

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
        usuarios = Usuario.query.filter_by(status='ativo').all()
        # Retornando apenas os campos necessários para evitar expor dados sensíveis
        usuarios_list = [{'id': u.id, 'login': u.login, 'nome': u.nome} for u in usuarios]
        return jsonify(usuarios_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/servidor/<string:matricula>')
@login_required
def get_servidor(matricula):
    servidor = Servidor.query.filter_by(matricula=matricula).first()
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

    servidores = Servidor.query.filter(Servidor.nome.ilike(f'%{query_nome}%')).limit(10).all()
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
    lotacoes = Lotacao.query.filter_by(ativo=True).order_by(Lotacao.nome).all()
    return jsonify([l.nome for l in lotacoes])

@app.route('/api/tipos_requerimento')
@login_required
def get_tipos_requerimento():
    tipos = TipoRequerimento.query.filter_by(ativo=True).order_by(TipoRequerimento.nome).all()
    return jsonify([t.nome for t in tipos])

@app.route('/api/protocolos/ultimoNumero/<int:ano>')
@login_required
def get_ultimo_numero(ano):
    # Filtra os números que correspondem ao padrão 'NNNN/ANO'
    numeros_do_ano = db.session.query(Protocolo.numero)\
        .filter(Protocolo.numero.like(f'%/{ano}'))\
        .all()

    # Extrai a parte numérica e encontra o máximo
    max_num = 0
    for num_str, in numeros_do_ano:
        try:
            num = int(num_str.split('/')[0])
            if num > max_num:
                max_num = num
        except (ValueError, IndexError):
            continue

    return jsonify({'ultimo': max_num})

@app.route('/api/protocolo/<int:protocolo_id>')
@login_required
def get_protocolo_api(protocolo_id):
    protocolo = Protocolo.query.get_or_404(protocolo_id)
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
    })

@app.route('/api/dashboard-data')
@login_required
def dashboard_data():
    # Get filter parameters from the request query string
    data_inicio_str = request.args.get('dataInicio')
    data_fim_str = request.args.get('dataFim')
    status = request.args.get('status')
    tipo = request.args.get('tipo')
    lotacao = request.args.get('lotacao')
    evolucao_periodo = request.args.get('evolucaoPeriodo', '30d')
    evolucao_agrupamento = request.args.get('evolucaoAgrupamento', 'day')

    # Base query for period-filtered stats
    base_query = Protocolo.query
    if data_inicio_str:
        base_query = base_query.filter(Protocolo.data_solicitacao >= datetime.strptime(data_inicio_str, '%Y-%m-%d').date())
    if data_fim_str:
        base_query = base_query.filter(Protocolo.data_solicitacao <= datetime.strptime(data_fim_str, '%Y-%m-%d').date())
    if status:
        base_query = base_query.filter(Protocolo.status == status)
    if tipo:
        base_query = base_query.filter(Protocolo.tipo_requerimento == tipo)
    if lotacao:
        base_query = base_query.filter(Protocolo.lotacao == lotacao)

    # --- Stats Cards Data ---
    novos_no_periodo_query = Protocolo.query
    if data_inicio_str:
        novos_no_periodo_query = novos_no_periodo_query.filter(Protocolo.data_solicitacao >= datetime.strptime(data_inicio_str, '%Y-%m-%d').date())
    else: # Default to last 7 days if no start date
        novos_no_periodo_query = novos_no_periodo_query.filter(Protocolo.data_solicitacao >= (datetime.now().date() - timedelta(days=7)))
    if data_fim_str:
        novos_no_periodo_query = novos_no_periodo_query.filter(Protocolo.data_solicitacao <= datetime.strptime(data_fim_str, '%Y-%m-%d').date())

    novos_no_periodo = novos_no_periodo_query.count()
    total_finalizados = base_query.filter(Protocolo.status.in_(['Finalizado', 'Concluído'])).count()
    pendentes_antigos = Protocolo.query.filter(
        Protocolo.data_solicitacao <= (datetime.now().date() - timedelta(days=15)),
        ~Protocolo.status.in_(['Finalizado', 'Concluído'])
    ).count()

    # --- Charts Data ---
    top_tipos = db.session.query(Protocolo.tipo_requerimento, func.count(Protocolo.id).label('total')).select_from(base_query.subquery()).group_by(Protocolo.tipo_requerimento).order_by(func.count(Protocolo.id).desc()).limit(5).all()
    todos_tipos = db.session.query(Protocolo.tipo_requerimento, func.count(Protocolo.id).label('total')).select_from(base_query.subquery()).group_by(Protocolo.tipo_requerimento).order_by(func.count(Protocolo.id).desc()).all()
    status_protocolos = db.session.query(Protocolo.status, func.count(Protocolo.id).label('total')).select_from(base_query.subquery()).group_by(Protocolo.status).order_by(Protocolo.status).all()

    # Evolution Chart Logic
    group_by_trunc = 'month' if evolucao_agrupamento == 'month' else 'day'
    evolucao_query = db.session.query(
        func.date_trunc(group_by_trunc, Protocolo.data_solicitacao).label('intervalo'),
        func.count(Protocolo.id).label('total')
    ).filter(Protocolo.data_solicitacao.isnot(None))

    # Apply filters to the evolution query
    if evolucao_periodo == '7d':
        evolucao_query = evolucao_query.filter(Protocolo.data_solicitacao >= (datetime.now().date() - timedelta(days=7)))
    elif evolucao_periodo == '30d':
        evolucao_query = evolucao_query.filter(Protocolo.data_solicitacao >= (datetime.now().date() - timedelta(days=30)))
    elif evolucao_periodo == 'month':
        evolucao_query = evolucao_query.filter(func.date_trunc('month', Protocolo.data_solicitacao) == func.date_trunc('month', datetime.now()))

    # Also apply the main dashboard filters to the evolution chart
    if status: evolucao_query = evolucao_query.filter(Protocolo.status == status)
    if tipo: evolucao_query = evolucao_query.filter(Protocolo.tipo_requerimento == tipo)
    if lotacao: evolucao_query = evolucao_query.filter(Protocolo.lotacao == lotacao)

    evolucao_protocolos = evolucao_query.group_by('intervalo').order_by('intervalo').all()

    # Prepare data for JSON response
    dashboard_stats = {
        'novosNoPeriodo': novos_no_periodo,
        'pendentesAntigos': pendentes_antigos,
        'totalFinalizados': total_finalizados,
        'topTipos': [{'tipo_requerimento': r[0], 'total': r[1]} for r in top_tipos],
        'todosTipos': [{'tipo_requerimento': r[0], 'total': r[1]} for r in todos_tipos],
        'statusProtocolos': [{'status': r[0], 'total': r[1]} for r in status_protocolos],
        'evolucaoProtocolos': [{'intervalo': r.intervalo.isoformat() if r.intervalo else None, 'total': r.total} for r in evolucao_protocolos]
    }

    return jsonify(dashboard_stats)

if __name__ == '__main__':
    # The port must be available. Railway provides the PORT env var.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
