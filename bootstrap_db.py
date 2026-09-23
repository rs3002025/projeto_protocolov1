"""Inicialização idempotente do esquema multicliente.

Registros legados são associados à organização definida em
DEFAULT_ORGANIZATION_SLUG (por padrão, ``prefeitura``).
"""
import os
import secrets

from sqlalchemy import inspect, text

from app import app, bcrypt, db
from models import Organizacao, Protocolo, Usuario


TENANT_TABLES = (
    'usuarios', 'protocolos', 'anexos', 'historico_protocolos', 'lotacoes',
    'servidores', 'tipos_requerimento', 'emails_sistema', 'movimentacoes',
    'chamados_suporte', 'mensagens_suporte',
)

SCHEMA_COLUMNS = {
    'organizacoes': {
        'logo_data': 'BLOB',
        'logo_mime_type': 'VARCHAR(80)',
        'logo_nome_arquivo': 'VARCHAR(255)',
        'logo_atualizada_em': 'TIMESTAMP',
        'municipio': 'VARCHAR(180)',
        'orgao': 'VARCHAR(180)',
        'rodape_documento': 'TEXT',
    },
    'usuarios': {
        'lotacao_id': 'BIGINT',
        'is_platform_admin': 'BOOLEAN DEFAULT FALSE NOT NULL',
    },
    'protocolos': {
        'prazo_em': 'DATE',
        'criado_por_id': 'INTEGER',
        'setor_atual_id': 'BIGINT',
        'arquivado_em': 'TIMESTAMP',
        'consulta_token': 'VARCHAR(64)',
    },
    'anexos': {
        'documento_chave': "VARCHAR(120) DEFAULT 'anexo' NOT NULL",
        'versao': 'INTEGER DEFAULT 1 NOT NULL',
        'enviado_por_id': 'INTEGER',
        'storage_backend': "VARCHAR(20) DEFAULT 'database' NOT NULL",
        'file_hash': 'VARCHAR(64)',
    },
    'historico_protocolos': {
        'usuario_id': 'INTEGER',
        'acao': "VARCHAR(80) DEFAULT 'ATUALIZACAO' NOT NULL",
    },
    'movimentacoes': {
        'destinatario_usuario_id': 'INTEGER',
    },
}


def bootstrap():
    slug = os.getenv('DEFAULT_ORGANIZATION_SLUG', 'prefeitura').strip().lower()
    nome = os.getenv('DEFAULT_ORGANIZATION_NAME', 'Prefeitura').strip()

    with app.app_context():
        # Cria tabelas novas e, em bancos vazios, todo o esquema completo.
        db.create_all()
        # Em bancos existentes, o modelo Organizacao já referencia os campos
        # de identidade. Eles precisam existir antes da primeira consulta ORM.
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())
        if 'organizacoes' in existing_tables:
            with db.engine.begin() as connection:
                columns = {column['name'] for column in inspect(connection).get_columns('organizacoes')}
                for column, sql_type in SCHEMA_COLUMNS['organizacoes'].items():
                    if column not in columns:
                        if column == 'logo_data' and db.engine.dialect.name == 'postgresql':
                            sql_type = 'BYTEA'
                        connection.execute(text(f'ALTER TABLE organizacoes ADD COLUMN {column} {sql_type}'))

        organizacao = Organizacao.query.filter_by(slug=slug).first()
        if not organizacao:
            organizacao = Organizacao(nome=nome, slug=slug, ativo=True)
            db.session.add(organizacao)
            db.session.commit()

        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())
        with db.engine.begin() as connection:
            for table in TENANT_TABLES:
                if table not in existing_tables:
                    continue
                columns = {column['name'] for column in inspect(connection).get_columns(table)}
                if 'tenant_id' not in columns:
                    connection.execute(text(f'ALTER TABLE {table} ADD COLUMN tenant_id INTEGER'))
                connection.execute(text(f'UPDATE {table} SET tenant_id = :tenant_id WHERE tenant_id IS NULL'), {'tenant_id': organizacao.id})

            for table, expected_columns in SCHEMA_COLUMNS.items():
                if table not in existing_tables:
                    continue
                columns = {column['name'] for column in inspect(connection).get_columns(table)}
                for column, sql_type in expected_columns.items():
                    if column not in columns:
                        if column == 'logo_data' and db.engine.dialect.name == 'postgresql':
                            sql_type = 'BYTEA'
                        connection.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {sql_type}'))

            if 'protocolos' in existing_tables:
                normalizacoes = {
                    'Aberto': 'PROTOCOLO GERADO', 'Em análise': 'EM ANÁLISE',
                    'EM ANALISE': 'EM ANÁLISE', 'Pendente de documento': 'PENDENTE DE DOCUMENTO',
                    'Finalizado': 'FINALIZADO', 'Concluído': 'CONCLUÍDO',
                    'Encaminhado': 'EM TRAMITAÇÃO',
                }
                for antigo, novo in normalizacoes.items():
                    connection.execute(text('UPDATE protocolos SET status = :novo WHERE status = :antigo'),
                                       {'novo': novo, 'antigo': antigo})

            if 'usuarios' in existing_tables:
                # Consolida os perfis antigos no novo perfil não administrativo.
                # Atribuições de tramitação devem ser explícitas e vinculadas a um setor.
                connection.execute(text(
                    "UPDATE usuarios SET tipo = 'protocolista' "
                    "WHERE tipo IN ('user', 'atendente', 'gestor')"
                ))

            if 'anexos' in existing_tables:
                connection.execute(text("UPDATE anexos SET storage_backend = 'database' WHERE storage_backend IS NULL"))

            if db.engine.dialect.name == 'postgresql':
                if 'anexos' in existing_tables:
                    connection.execute(text('ALTER TABLE anexos ALTER COLUMN file_data DROP NOT NULL'))
                connection.execute(text('ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS usuarios_login_key'))
                connection.execute(text('ALTER TABLE protocolos DROP CONSTRAINT IF EXISTS protocolos_numero_key'))
                for table in TENANT_TABLES:
                    if table in existing_tables:
                        connection.execute(text(f'ALTER TABLE {table} ALTER COLUMN tenant_id SET NOT NULL'))

                statements = (
                    'CREATE UNIQUE INDEX IF NOT EXISTS uq_usuario_tenant_login ON usuarios (tenant_id, login)',
                    'CREATE UNIQUE INDEX IF NOT EXISTS uq_protocolo_tenant_numero ON protocolos (tenant_id, numero)',
                    'CREATE UNIQUE INDEX IF NOT EXISTS uq_lotacao_tenant_nome ON lotacoes (tenant_id, nome)',
                    'CREATE UNIQUE INDEX IF NOT EXISTS uq_servidor_tenant_matricula ON servidores (tenant_id, matricula)',
                    'CREATE UNIQUE INDEX IF NOT EXISTS uq_tipo_tenant_nome ON tipos_requerimento (tenant_id, nome)',
                    'CREATE UNIQUE INDEX IF NOT EXISTS uq_protocolo_consulta_token ON protocolos (consulta_token)',
                )
                for statement in statements:
                    connection.execute(text(statement))

        # Tokens públicos são opacos e exclusivos; registros antigos recebem um
        # token durante a atualização antes de o aplicativo iniciar.
        for protocolo in Protocolo.query.filter(Protocolo.consulta_token.is_(None)).all():
            protocolo.consulta_token = secrets.token_urlsafe(32)

        # Ambientes novos podem receber um administrador inicial por variáveis
        # efêmeras. Em bancos já povoados nenhuma credencial é alterada.
        admin_password = os.getenv('BOOTSTRAP_ADMIN_PASSWORD', '')
        admin_login = os.getenv('BOOTSTRAP_ADMIN_LOGIN', 'admin').strip() or 'admin'
        if admin_password and not Usuario.query.filter_by(
                tenant_id=organizacao.id, login=admin_login).first():
            admin_name = os.getenv('BOOTSTRAP_ADMIN_NAME', 'Administrador').strip() or 'Administrador'
            db.session.add(Usuario(
                tenant_id=organizacao.id,
                nome=admin_name.split()[0],
                nome_completo=admin_name,
                login=admin_login,
                email=os.getenv('BOOTSTRAP_ADMIN_EMAIL', 'admin@localhost.invalid'),
                senha=bcrypt.generate_password_hash(admin_password).decode('utf-8'),
                tipo='admin',
                status='ativo',
                is_platform_admin=True,
            ))
        db.session.commit()


if __name__ == '__main__':
    bootstrap()
