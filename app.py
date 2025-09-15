import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt

app = Flask(__name__)

# --- Configuration ---
# Secret key for session management (e.g., for Flask-Login)
app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-segura-e-dificil-de-adivinhar' # Replace with a real secret key

# Database configuration - Hardcoded as a workaround for .env issues
DATABASE_URL = "postgresql://postgres:jQxcYjVcLejOYCtPXmPGweRyoQPxQdnt@metro.proxy.rlwy.net:34866/railway"
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
from flask import send_file, Response
from werkzeug.utils import secure_filename
import io
from openpyxl import Workbook
from forms import LoginForm, RegistrationForm, ProtocoloForm, AnexoForm
from models import Usuario, Protocolo, HistoricoProtocolo, Anexo, db

# --- Routes ---
@app.route("/")
@app.route("/home")
@login_required
def home():
    protocolos = Protocolo.query.order_by(Protocolo.data_solicitacao.desc()).limit(10).all()
    return render_template('home.html', protocolos=protocolos)

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

# --- Rotas de Protocolo ---

@app.route("/protocolos")
@login_required
def listar_protocolos():
    page = request.args.get('page', 1, type=int)
    protocolos = Protocolo.query.order_by(Protocolo.id.desc()).paginate(page=page, per_page=10)
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

# --- Rota de Backup ---

@app.route('/protocolos/backup/excel')
@login_required
def backup_excel():
    """Gera um arquivo Excel com todos os protocolos."""
    protocolos = Protocolo.query.order_by(Protocolo.id.asc()).all()

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

if __name__ == '__main__':
    # The port must be available. Railway provides the PORT env var.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
