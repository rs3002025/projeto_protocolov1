from app import db, login_manager
from flask_login import UserMixin
from sqlalchemy.dialects.postgresql import BYTEA

# Flask-Login requires this callback to load a user from the session
@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nome_completo = db.Column(db.Text)
    cpf = db.Column(db.String)
    status = db.Column(db.Text, default='ativo')
    nome = db.Column(db.Text, nullable=False)
    login = db.Column(db.Text, unique=True, nullable=False)
    senha = db.Column(db.Text, nullable=False)
    tipo = db.Column(db.Text, nullable=False)
    email = db.Column(db.Text)

class Protocolo(db.Model):
    __tablename__ = 'protocolos'
    id = db.Column(db.Integer, primary_key=True)
    visto = db.Column(db.Boolean, default=False)
    numero = db.Column(db.String, unique=True)
    nome = db.Column(db.String)
    matricula = db.Column(db.String)
    endereco = db.Column(db.Text)
    municipio = db.Column(db.String)
    bairro = db.Column(db.String)
    cep = db.Column(db.String)
    telefone = db.Column(db.String)
    cpf = db.Column(db.String)
    rg = db.Column(db.String)
    cargo = db.Column(db.String)
    lotacao = db.Column(db.String)
    unidade_exercicio = db.Column(db.String)
    tipo_requerimento = db.Column(db.String)
    requer_ao = db.Column(db.Text)
    data_solicitacao = db.Column(db.Date)
    observacoes = db.Column(db.Text)
    responsavel = db.Column(db.String)
    data_envio = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())
    status = db.Column(db.String, default='Aberto')

    # Relationships
    anexos = db.relationship('Anexo', backref='protocolo', lazy=True, cascade="all, delete-orphan")
    historico = db.relationship('HistoricoProtocolo', backref='protocolo', lazy=True, cascade="all, delete-orphan")

class Anexo(db.Model):
    __tablename__ = 'anexos'
    id = db.Column(db.BigInteger, primary_key=True)
    protocolo_id = db.Column(db.BigInteger, db.ForeignKey('protocolos.id'), nullable=False)
    file_name = db.Column(db.Text, nullable=False)
    storage_path = db.Column(db.Text, nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False)
    mime_type = db.Column(db.Text, nullable=False)
    file_data = db.Column(BYTEA, nullable=False)
    created_at = db.Column(db.TIMESTAMP(timezone=True), server_default=db.func.now())

class HistoricoProtocolo(db.Model):
    __tablename__ = 'historico_protocolos'
    id = db.Column(db.Integer, primary_key=True)
    protocolo_id = db.Column(db.Integer, db.ForeignKey('protocolos.id'), nullable=True)
    status = db.Column(db.String)
    responsavel = db.Column(db.String)
    observacao = db.Column(db.Text)
    data_movimentacao = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

class Lotacao(db.Model):
    __tablename__ = 'lotacoes'
    id = db.Column(db.BigInteger, primary_key=True)
    nome = db.Column(db.Text, nullable=False)
    ativo = db.Column(db.Boolean, default=True)

class Servidor(db.Model):
    __tablename__ = 'servidores'
    id = db.Column(db.BigInteger, primary_key=True)
    matricula = db.Column(db.Text, nullable=False)
    nome = db.Column(db.Text)
    lotacao = db.Column(db.Text)
    cargo = db.Column(db.Text)
    unidade_de_exercicio = db.Column(db.Text)

class TipoRequerimento(db.Model):
    __tablename__ = 'tipos_requerimento'
    id = db.Column(db.BigInteger, primary_key=True)
    nome = db.Column(db.Text, nullable=False)
    ativo = db.Column(db.Boolean, default=True)

class EmailSistema(db.Model):
    __tablename__ = 'emails_sistema'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.Text, nullable=False)
    email = db.Column(db.Text, nullable=False)
