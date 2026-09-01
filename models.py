from app import db, login_manager
from flask_login import UserMixin
import secrets

ID_TYPE = db.BigInteger().with_variant(db.Integer, 'sqlite')

# Flask-Login requires this callback to load a user from the session
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))

class Organizacao(db.Model):
    __tablename__ = 'organizacoes'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(180), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp(), nullable=False)
    logo_data = db.Column(db.LargeBinary)
    logo_mime_type = db.Column(db.String(80))
    logo_nome_arquivo = db.Column(db.String(255))
    logo_atualizada_em = db.Column(db.TIMESTAMP)

class TenantMixin:
    tenant_id = db.Column(db.Integer, db.ForeignKey('organizacoes.id'), nullable=False, index=True)

class Usuario(TenantMixin, db.Model, UserMixin):
    __tablename__ = 'usuarios'
    __table_args__ = (db.UniqueConstraint('tenant_id', 'login', name='uq_usuario_tenant_login'),)
    id = db.Column(db.Integer, primary_key=True)
    nome_completo = db.Column(db.Text)
    cpf = db.Column(db.String)
    status = db.Column(db.Text, default='ativo')
    nome = db.Column(db.Text, nullable=False)
    login = db.Column(db.Text, nullable=False)
    senha = db.Column(db.Text, nullable=False)
    tipo = db.Column(db.Text, nullable=False)
    email = db.Column(db.Text)
    lotacao_id = db.Column(ID_TYPE, db.ForeignKey('lotacoes.id'))
    organizacao = db.relationship('Organizacao')

    @property
    def is_active(self):
        return self.status == 'ativo' and self.organizacao is not None and self.organizacao.ativo

class Protocolo(TenantMixin, db.Model):
    __tablename__ = 'protocolos'
    __table_args__ = (db.UniqueConstraint('tenant_id', 'numero', name='uq_protocolo_tenant_numero'),)
    id = db.Column(db.Integer, primary_key=True)
    visto = db.Column(db.Boolean, default=False)
    numero = db.Column(db.String)
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
    prazo_em = db.Column(db.Date)
    observacoes = db.Column(db.Text)
    responsavel = db.Column(db.String)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    setor_atual_id = db.Column(ID_TYPE, db.ForeignKey('lotacoes.id'))
    data_envio = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())
    status = db.Column(db.String, default='Aberto')
    arquivado_em = db.Column(db.TIMESTAMP)
    consulta_token = db.Column(db.String(64), unique=True, nullable=False,
                               default=lambda: secrets.token_urlsafe(32), index=True)

    # Relationships
    anexos = db.relationship('Anexo', backref='protocolo', lazy=True, cascade="all, delete-orphan")
    historico = db.relationship('HistoricoProtocolo', backref='protocolo', lazy=True, cascade="all, delete-orphan")
    movimentacoes = db.relationship('Movimentacao', backref='protocolo', lazy=True, cascade="all, delete-orphan")
    setor_atual = db.relationship('Lotacao', foreign_keys=[setor_atual_id])

class Anexo(TenantMixin, db.Model):
    __tablename__ = 'anexos'
    id = db.Column(ID_TYPE, primary_key=True)
    protocolo_id = db.Column(ID_TYPE, db.ForeignKey('protocolos.id'), nullable=False)
    file_name = db.Column(db.Text, nullable=False)
    storage_path = db.Column(db.Text, nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False)
    mime_type = db.Column(db.Text, nullable=False)
    file_data = db.Column(db.LargeBinary, nullable=False)
    documento_chave = db.Column(db.String(120), nullable=False, default='anexo')
    versao = db.Column(db.Integer, nullable=False, default=1)
    enviado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    created_at = db.Column(db.TIMESTAMP(timezone=True), server_default=db.func.now())

class HistoricoProtocolo(TenantMixin, db.Model):
    __tablename__ = 'historico_protocolos'
    id = db.Column(db.Integer, primary_key=True)
    protocolo_id = db.Column(db.Integer, db.ForeignKey('protocolos.id'), nullable=True)
    status = db.Column(db.String)
    responsavel = db.Column(db.String)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    acao = db.Column(db.String(80), nullable=False, default='ATUALIZACAO')
    observacao = db.Column(db.Text)
    data_movimentacao = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

class Movimentacao(TenantMixin, db.Model):
    __tablename__ = 'movimentacoes'
    id = db.Column(db.Integer, primary_key=True)
    protocolo_id = db.Column(db.Integer, db.ForeignKey('protocolos.id'), nullable=False)
    setor_origem_id = db.Column(ID_TYPE, db.ForeignKey('lotacoes.id'))
    setor_destino_id = db.Column(ID_TYPE, db.ForeignKey('lotacoes.id'), nullable=False)
    enviado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    recebido_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    enviado_em = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp(), nullable=False)
    recebido_em = db.Column(db.TIMESTAMP)
    observacao = db.Column(db.Text)
    setor_origem = db.relationship('Lotacao', foreign_keys=[setor_origem_id])
    setor_destino = db.relationship('Lotacao', foreign_keys=[setor_destino_id])

class ConsultaPublicaTentativa(db.Model):
    __tablename__ = 'consulta_publica_tentativas'
    __table_args__ = (db.UniqueConstraint('protocolo_id', 'identificador_hash',
                                          name='uq_consulta_protocolo_identificador'),)
    id = db.Column(db.Integer, primary_key=True)
    protocolo_id = db.Column(db.Integer, db.ForeignKey('protocolos.id'), nullable=False, index=True)
    identificador_hash = db.Column(db.String(64), nullable=False)
    tentativas = db.Column(db.Integer, nullable=False, default=0)
    janela_iniciada_em = db.Column(db.TIMESTAMP, nullable=False, default=db.func.current_timestamp())
    bloqueado_ate = db.Column(db.TIMESTAMP)
    atualizado_em = db.Column(db.TIMESTAMP, nullable=False, default=db.func.current_timestamp(),
                              onupdate=db.func.current_timestamp())

class Lotacao(TenantMixin, db.Model):
    __tablename__ = 'lotacoes'
    __table_args__ = (db.UniqueConstraint('tenant_id', 'nome', name='uq_lotacao_tenant_nome'),)
    id = db.Column(ID_TYPE, primary_key=True)
    nome = db.Column(db.Text, nullable=False)
    ativo = db.Column(db.Boolean, default=True)

class Servidor(TenantMixin, db.Model):
    __tablename__ = 'servidores'
    __table_args__ = (db.UniqueConstraint('tenant_id', 'matricula', name='uq_servidor_tenant_matricula'),)
    id = db.Column(ID_TYPE, primary_key=True)
    matricula = db.Column(db.Text, nullable=False)
    nome = db.Column(db.Text)
    lotacao = db.Column(db.Text)
    cargo = db.Column(db.Text)
    unidade_de_exercicio = db.Column(db.Text)

class TipoRequerimento(TenantMixin, db.Model):
    __tablename__ = 'tipos_requerimento'
    __table_args__ = (db.UniqueConstraint('tenant_id', 'nome', name='uq_tipo_tenant_nome'),)
    id = db.Column(ID_TYPE, primary_key=True)
    nome = db.Column(db.Text, nullable=False)
    ativo = db.Column(db.Boolean, default=True)

class EmailSistema(TenantMixin, db.Model):
    __tablename__ = 'emails_sistema'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.Text, nullable=False)
    email = db.Column(db.Text, nullable=False)
