from .extensions import db
from sqlalchemy.sql import func
from werkzeug.security import generate_password_hash, check_password_hash

# Modelo para os Tenants (clientes) - ficará no schema público
class Tenant(db.Model):
    __tablename__ = 'tenants'
    __table_args__ = {'schema': 'public'}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    client_code = db.Column(db.String(50), unique=True, nullable=False)
    schema_name = db.Column(db.String(50), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f'<Tenant {self.name}>'

# Modelos que existirão dentro do schema de cada tenant

class Usuario(db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    nome = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='user') # ex: 'user', 'admin'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Servidor(db.Model):
    __tablename__ = 'servidores'

    id = db.Column(db.Integer, primary_key=True)
    matricula = db.Column(db.String(50), unique=True, nullable=False)
    nome = db.Column(db.String(120), nullable=False)
    lotacao = db.Column(db.String(120))
    cargo = db.Column(db.String(120))
    unidade_de_exercicio = db.Column(db.String(120))

class Protocolo(db.Model):
    __tablename__ = 'protocolos'

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(50))
    nome = db.Column(db.String(120), nullable=False)
    matricula = db.Column(db.String(50))
    endereco = db.Column(db.String(255))
    municipio = db.Column(db.String(100))
    bairro = db.Column(db.String(100))
    cep = db.Column(db.String(20))
    telefone = db.Column(db.String(20))
    cpf = db.Column(db.String(20))
    rg = db.Column(db.String(20))
    cargo = db.Column(db.String(120))
    lotacao = db.Column(db.String(120))
    unidade_exercicio = db.Column(db.String(120))
    tipo_requerimento = db.Column(db.String(120))
    requer_ao = db.Column(db.String(120))
    data_solicitacao = db.Column(db.Date, nullable=False)
    observacoes = db.Column(db.Text)
    status = db.Column(db.String(50), nullable=False, default='Aberto')
    responsavel = db.Column(db.String(120))
    visto = db.Column(db.Boolean, default=False)

    historico = db.relationship('HistoricoProtocolo', backref='protocolo', lazy=True, cascade="all, delete-orphan")
    anexos = db.relationship('Anexo', backref='protocolo', lazy=True, cascade="all, delete-orphan")

class HistoricoProtocolo(db.Model):
    __tablename__ = 'historico_protocolos'

    id = db.Column(db.Integer, primary_key=True)
    protocolo_id = db.Column(db.Integer, db.ForeignKey('protocolos.id'), nullable=False)
    status = db.Column(db.String(50))
    responsavel = db.Column(db.String(120))
    observacao = db.Column(db.Text)
    data_movimentacao = db.Column(db.DateTime(timezone=True), server_default=func.now())

class Anexo(db.Model):
    __tablename__ = 'anexos'

    id = db.Column(db.Integer, primary_key=True)
    protocolo_id = db.Column(db.Integer, db.ForeignKey('protocolos.id'), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    file_data = db.Column(db.LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
