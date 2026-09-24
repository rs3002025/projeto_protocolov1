from app import db, login_manager
from flask_login import UserMixin
import secrets

ID_TYPE = db.BigInteger().with_variant(db.Integer, 'sqlite')

# Flask-Login requires this callback to load a user from the session
@login_manager.user_loader
def load_user(user_id):
    user = db.session.get(Usuario, int(user_id))
    return user if user and user.is_active else None

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
    municipio = db.Column(db.String(180))
    orgao = db.Column(db.String(180))
    rodape_documento = db.Column(db.Text)
    emissao_eletronica_protocolista_enabled = db.Column(db.Boolean, nullable=False, default=False)
    portal_servidor_remoto_enabled = db.Column(db.Boolean, nullable=False, default=False)
    nivel_garantia_assinatura = db.Column(db.String(20), nullable=False, default='interno')


class OrganizacaoCapacidadeEvento(db.Model):
    """Histórico append-only das capacidades liberadas pelo administrador geral."""
    __tablename__ = 'organizacao_capacidade_eventos'
    id = db.Column(ID_TYPE, primary_key=True)
    organizacao_id = db.Column(db.Integer, db.ForeignKey('organizacoes.id'), nullable=False, index=True)
    alterado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, index=True)
    emissao_eletronica_protocolista_enabled = db.Column(db.Boolean, nullable=False)
    portal_servidor_remoto_enabled = db.Column(db.Boolean, nullable=False)
    nivel_garantia_assinatura = db.Column(db.String(20), nullable=False)
    motivo = db.Column(db.String(500))
    criado_em = db.Column(db.TIMESTAMP(timezone=True), server_default=db.func.now(), nullable=False)

    organizacao = db.relationship('Organizacao', foreign_keys=[organizacao_id])
    alterado_por = db.relationship('Usuario', foreign_keys=[alterado_por_id])

class TenantMixin:
    tenant_id = db.Column(db.Integer, db.ForeignKey('organizacoes.id'), nullable=False, index=True)

class Usuario(TenantMixin, db.Model, UserMixin):
    __tablename__ = 'usuarios'
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'login', name='uq_usuario_tenant_login'),
        db.UniqueConstraint('tenant_id', 'servidor_id', name='uq_usuario_tenant_servidor'),
    )
    id = db.Column(db.Integer, primary_key=True)
    nome_completo = db.Column(db.Text)
    cpf = db.Column(db.String)
    status = db.Column(db.Text, default='ativo')
    nome = db.Column(db.Text, nullable=False)
    login = db.Column(db.Text, nullable=False)
    senha = db.Column(db.Text, nullable=False)
    tipo = db.Column(db.Text, nullable=False)
    is_platform_admin = db.Column(db.Boolean, nullable=False, default=False)
    email = db.Column(db.Text)
    lotacao_id = db.Column(ID_TYPE, db.ForeignKey('lotacoes.id'))
    servidor_id = db.Column(ID_TYPE, db.ForeignKey('servidores.id'))
    organizacao = db.relationship('Organizacao')
    servidor = db.relationship('Servidor', foreign_keys=[servidor_id])

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
    requerente_servidor_id = db.Column(ID_TYPE, db.ForeignKey('servidores.id'))
    emitido_por_usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    retificacao_pendente = db.Column(db.Boolean, nullable=False, default=False)
    modalidade_abertura = db.Column(db.String(30), nullable=False, default='presencial_protocolista')
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
    criado_por = db.relationship('Usuario', foreign_keys=[criado_por_id])
    emitido_por = db.relationship('Usuario', foreign_keys=[emitido_por_usuario_id])
    requerente_servidor = db.relationship('Servidor', foreign_keys=[requerente_servidor_id])
    emissoes_eletronicas = db.relationship('EmissaoEletronica', back_populates='protocolo',
                                           cascade='all, delete-orphan',
                                           order_by='EmissaoEletronica.versao')

    @property
    def emissao_eletronica(self):
        """Versão autenticada mais recente, preservando compatibilidade com as telas."""
        return self.emissoes_eletronicas[-1] if self.emissoes_eletronicas else None


class EmissaoEletronica(TenantMixin, db.Model):
    """Evidência imutável da emissão eletrônica do requerimento/protocolo."""
    __tablename__ = 'emissoes_eletronicas'
    id = db.Column(ID_TYPE, primary_key=True)
    __table_args__ = (db.UniqueConstraint('tenant_id', 'protocolo_id', 'versao',
                                          name='uq_emissao_protocolo_versao'),)
    protocolo_id = db.Column(ID_TYPE, db.ForeignKey('protocolos.id'), nullable=False, index=True)
    versao = db.Column(db.Integer, nullable=False, default=1)
    substitui_emissao_id = db.Column(ID_TYPE, db.ForeignKey('emissoes_eletronicas.id'))
    emitido_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, index=True)
    pdf_anexo_id = db.Column(ID_TYPE, db.ForeignKey('anexos.id'), nullable=False, unique=True)
    token_publico = db.Column(db.String(64), nullable=False, unique=True, index=True)
    codigo_publico = db.Column(db.String(20), nullable=False, unique=True, index=True)
    pdf_sha256 = db.Column(db.String(64), nullable=False)
    metodo = db.Column(db.String(40), nullable=False, default='senha_individual')
    nivel_garantia = db.Column(db.String(20), nullable=False, default='interno')
    declaracao = db.Column(db.Text, nullable=False)
    nome_emitente = db.Column(db.String(180), nullable=False)
    login_emitente = db.Column(db.String(80), nullable=False)
    ip_hash = db.Column(db.String(64), nullable=False)
    user_agent_hash = db.Column(db.String(64), nullable=False)
    emitido_em = db.Column(db.TIMESTAMP(timezone=True), server_default=db.func.now(), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='VALIDA')
    cancelado_em = db.Column(db.TIMESTAMP(timezone=True))
    cancelado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    motivo_cancelamento = db.Column(db.Text)

    protocolo = db.relationship('Protocolo', back_populates='emissoes_eletronicas', foreign_keys=[protocolo_id])
    emitido_por = db.relationship('Usuario', foreign_keys=[emitido_por_id])
    pdf_anexo = db.relationship('Anexo', foreign_keys=[pdf_anexo_id])
    substitui_emissao = db.relationship('EmissaoEletronica', remote_side=[id],
                                        foreign_keys=[substitui_emissao_id])

class Anexo(TenantMixin, db.Model):
    __tablename__ = 'anexos'
    id = db.Column(ID_TYPE, primary_key=True)
    protocolo_id = db.Column(ID_TYPE, db.ForeignKey('protocolos.id'), nullable=False)
    file_name = db.Column(db.Text, nullable=False)
    storage_path = db.Column(db.Text, nullable=False)
    storage_backend = db.Column(db.String(20), nullable=False, default='database')
    file_hash = db.Column(db.String(64))
    file_size = db.Column(db.BigInteger, nullable=False)
    mime_type = db.Column(db.Text, nullable=False)
    file_data = db.Column(db.LargeBinary)
    documento_chave = db.Column(db.String(120), nullable=False, default='anexo')
    versao = db.Column(db.Integer, nullable=False, default=1)
    enviado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    enviado_por = db.relationship('Usuario', foreign_keys=[enviado_por_id])
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
    destinatario_usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    enviado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    recebido_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    enviado_em = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp(), nullable=False)
    recebido_em = db.Column(db.TIMESTAMP)
    observacao = db.Column(db.Text)
    setor_origem = db.relationship('Lotacao', foreign_keys=[setor_origem_id])
    setor_destino = db.relationship('Lotacao', foreign_keys=[setor_destino_id])
    destinatario_usuario = db.relationship('Usuario', foreign_keys=[destinatario_usuario_id])

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


class LoginTentativa(db.Model):
    __tablename__ = 'login_tentativas'
    id = db.Column(db.Integer, primary_key=True)
    identificador_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
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


class ChamadoSuporte(TenantMixin, db.Model):
    __tablename__ = 'chamados_suporte'
    id = db.Column(ID_TYPE, primary_key=True)
    assunto = db.Column(db.String(180), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    categoria = db.Column(db.String(40), nullable=False, default='OUTRO')
    prioridade = db.Column(db.String(20), nullable=False, default='NORMAL')
    status = db.Column(db.String(30), nullable=False, default='ABERTO', index=True)
    aberto_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, index=True)
    atribuido_a_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), index=True)
    criado_em = db.Column(db.TIMESTAMP(timezone=True), server_default=db.func.now(), nullable=False)
    atualizado_em = db.Column(db.TIMESTAMP(timezone=True), server_default=db.func.now(),
                              onupdate=db.func.now(), nullable=False)
    encerrado_em = db.Column(db.TIMESTAMP(timezone=True))

    aberto_por = db.relationship('Usuario', foreign_keys=[aberto_por_id])
    atribuido_a = db.relationship('Usuario', foreign_keys=[atribuido_a_id])
    mensagens = db.relationship('MensagemSuporte', backref='chamado', lazy=True,
                                cascade='all, delete-orphan', order_by='MensagemSuporte.criado_em')


class MensagemSuporte(TenantMixin, db.Model):
    __tablename__ = 'mensagens_suporte'
    id = db.Column(ID_TYPE, primary_key=True)
    chamado_id = db.Column(ID_TYPE, db.ForeignKey('chamados_suporte.id'), nullable=False, index=True)
    autor_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    mensagem = db.Column(db.Text, nullable=False)
    criado_em = db.Column(db.TIMESTAMP(timezone=True), server_default=db.func.now(), nullable=False)

    autor = db.relationship('Usuario', foreign_keys=[autor_id])

