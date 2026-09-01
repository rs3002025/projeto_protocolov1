"""Inicialização idempotente do esquema multicliente.

Registros legados são associados à organização definida em
DEFAULT_ORGANIZATION_SLUG (por padrão, ``prefeitura``).
"""
import os
import secrets

from sqlalchemy import inspect, text

from app import app, db
from models import Organizacao, Protocolo


TENANT_TABLES = (
    'usuarios', 'protocolos', 'anexos', 'historico_protocolos', 'lotacoes',
    'servidores', 'tipos_requerimento', 'emails_sistema', 'movimentacoes',
)

SCHEMA_COLUMNS = {
    'usuarios': {
        'lotacao_id': 'BIGINT',
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
    },
    'historico_protocolos': {
        'usuario_id': 'INTEGER',
        'acao': "VARCHAR(80) DEFAULT 'ATUALIZACAO' NOT NULL",
    },
}


def bootstrap():
    slug = os.getenv('DEFAULT_ORGANIZATION_SLUG', 'prefeitura').strip().lower()
    nome = os.getenv('DEFAULT_ORGANIZATION_NAME', 'Prefeitura').strip()

    with app.app_context():
        # Cria tabelas novas e, em bancos vazios, todo o esquema completo.
        db.create_all()
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
                        connection.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {sql_type}'))

            if db.engine.dialect.name == 'postgresql':
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
        db.session.commit()


if __name__ == '__main__':
    bootstrap()
