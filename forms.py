from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError
from models import Usuario

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
        user = Usuario.query.filter_by(login=login.data).first()
        if user:
            raise ValidationError('Esse login já está em uso. Por favor, escolha outro.')


from wtforms import StringField, TextAreaField, DateField, SubmitField
from wtforms.validators import Optional
from flask_wtf.file import FileField, FileRequired, FileAllowed

class LoginForm(FlaskForm):
    """Formulário de Login de Usuário"""
    login = StringField('Login', validators=[DataRequired()])
    senha = PasswordField('Senha', validators=[DataRequired()])
    remember = BooleanField('Lembrar-me')
    submit = SubmitField('Entrar')

class ProtocoloForm(FlaskForm):
    """Formulário para criar ou editar um protocolo."""
    numero = StringField('Número do Protocolo', validators=[DataRequired()])
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

class AnexoForm(FlaskForm):
    """Formulário para upload de anexos."""
    anexo = FileField('Selecione o arquivo', validators=[
        FileRequired(message='Nenhum arquivo selecionado!'),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'csv'], 'Tipo de arquivo não permitido!')
    ])
    submit_anexo = SubmitField('Enviar Anexo')
