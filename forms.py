from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError
from models import Usuario
from flask_login import current_user

class RegistrationForm(FlaskForm):
    """Formulário de Registro de Usuário"""
    nome_completo = StringField('Nome Completo', validators=[DataRequired(), Length(min=2, max=150)])
    login = StringField('Login de Acesso', validators=[DataRequired(), Length(min=4, max=25)])
    senha = PasswordField('Senha', validators=[DataRequired(), Length(min=6)])
    confirmar_senha = PasswordField('Confirmar Senha', validators=[DataRequired(), EqualTo('senha', message='As senhas devem ser iguais.')])
    # O campo 'tipo' (admin, user) pode ser definido administrativamente, não no registro público
    submit = SubmitField('Registrar')

    def validate_login(self, login):
        """Verifica se o login já está em uso."""
        tenant_id = current_user.tenant_id if current_user.is_authenticated else None
        user = Usuario.query.filter_by(tenant_id=tenant_id, login=login.data).first()
        if user:
            raise ValidationError('Esse login já está em uso. Por favor, escolha outro.')


from wtforms import StringField, TextAreaField, DateField, SubmitField
from wtforms.validators import Optional
from flask_wtf.file import FileField, FileRequired, FileAllowed

class LoginForm(FlaskForm):
    """Formulário de Login de Usuário"""
    organizacao = StringField('Organização', validators=[DataRequired(), Length(min=2, max=80)])
    login = StringField('Login', validators=[DataRequired()])
    senha = PasswordField('Senha', validators=[DataRequired()])
    remember = BooleanField('Lembrar-me')
    submit = SubmitField('Entrar')

class ConsultaPublicaForm(FlaskForm):
    matricula = StringField('Confirme a matrícula', validators=[
        DataRequired(), Length(min=1, max=80)
    ])
    submit = SubmitField('Consultar protocolo')

class ProtocoloForm(FlaskForm):
    """Formulário para criar ou editar um protocolo."""
    numero = StringField('Número do Protocolo', validators=[Optional()])
    nome = StringField('Nome do Requerente', validators=[DataRequired()])
    matricula = StringField('Matrícula', validators=[Optional()])
    endereco = TextAreaField('Endereço', validators=[Optional()])
    municipio = StringField('Município', validators=[Optional()])
    bairro = StringField('Bairro', validators=[Optional()])
    cep = StringField('CEP', validators=[Optional()])
    telefone = StringField('Telefone', validators=[Optional()])
    cpf = StringField('CPF', validators=[Optional()])
    rg = StringField('RG', validators=[Optional()])
    cargo = StringField('Cargo', validators=[Optional()])
    lotacao = StringField('Lotação', validators=[Optional()])
    unidade_exercicio = StringField('Unidade de Exercício', validators=[Optional()])
    tipo_requerimento = StringField('Tipo de Requerimento', validators=[DataRequired()])
    requer_ao = StringField('Requer A', validators=[Optional()])
    data_solicitacao = DateField('Data da Solicitação (AAAA-MM-DD)', format='%Y-%m-%d', validators=[DataRequired()])
    observacoes = TextAreaField('Observações/Complemento', validators=[Optional()])
    responsavel = StringField('Responsável Inicial', validators=[Optional()])
    status = StringField('Status Inicial', default='Aberto', validators=[Optional()])
    submit = SubmitField('Salvar Protocolo')

from wtforms import SelectField

class AnexoForm(FlaskForm):
    """Formulário para upload de anexos."""
    anexo = FileField('Selecione o arquivo', validators=[
        FileRequired(message='Nenhum arquivo selecionado!'),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'csv'], 'Tipo de arquivo não permitido!')
    ])
    submit_anexo = SubmitField('Enviar Anexo')

class AdminUserCreationForm(FlaskForm):
    """Formulário para administradores criarem usuários."""
    nome_completo = StringField('Nome Completo', validators=[DataRequired()])
    login = StringField('Login', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired()])
    senha = PasswordField('Senha', validators=[DataRequired(), Length(min=6)])
    tipo = SelectField('Perfil', choices=[
        ('consulta', 'Consulta'),
        ('atendente', 'Atendente'),
        ('gestor', 'Gestor'),
        ('admin', 'Administrador'),
    ], validators=[DataRequired()])
    lotacao_id = SelectField('Setor/Lotação', coerce=int, choices=[], validators=[Optional()])
    submit = SubmitField('Criar Usuário')

    def validate_login(self, login):
        if Usuario.query.filter_by(tenant_id=current_user.tenant_id, login=login.data).first():
            raise ValidationError('Este login já está em uso.')

class AdminListItemForm(FlaskForm):
    """Formulário genérico para adicionar itens de lista (Lotação, Tipo)."""
    nome = StringField('Nome', validators=[DataRequired()])
    submit = SubmitField('Adicionar')

class BrandingForm(FlaskForm):
    logo = FileField('Logo da organização', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'webp'], 'Envie uma imagem PNG, JPG ou WebP.')
    ])
    salvar = SubmitField('Salvar logo')
    remover = SubmitField('Restaurar logo padrão')
