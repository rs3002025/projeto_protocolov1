import sys
from flask.cli import FlaskGroup
from sqlalchemy import text
from app import create_app
from app.extensions import db
from app.models import Tenant, Usuario
from app.core.tenant_management import create_tenant_schema_and_tables

cli = FlaskGroup(create_app=create_app)

@cli.command("init-db")
def init_db():
    """Inicializa o banco de dados, cria schemas e tabelas para os tenants."""
    app = cli.create_app()
    tenants_to_create = [
        {'name': 'Cliente Alpha', 'client_code': 'alpha', 'schema_name': 'alpha'},
        {'name': 'Cliente Beta', 'client_code': 'beta', 'schema_name': 'beta'},
        {'name': 'Cliente Gamma', 'client_code': 'gamma', 'schema_name': 'gamma'},
        {'name': 'Cliente Delta', 'client_code': 'delta', 'schema_name': 'delta'},
        {'name': 'Cliente Epsilon', 'client_code': 'epsilon', 'schema_name': 'epsilon'},
    ]

    with app.app_context():
        print("!! AVISO: Apagando todos os schemas e tabelas existentes (modo de desenvolvimento) !!")
        tenants_to_drop = reversed(tenants_to_create)
        for tenant_info in tenants_to_drop:
            schema_name = tenant_info['schema_name']
            db.session.execute(text(f'DROP SCHEMA IF EXISTS {schema_name} CASCADE'))
        db.session.execute(text('DROP TABLE IF EXISTS public.tenants CASCADE'))
        db.session.commit()
        print("!! Schemas e tabelas antigos foram removidos. !!\n")

        print("Verificando/Criando tabela 'tenants' no schema 'public'...")
        Tenant.__table__.create(bind=db.engine, checkfirst=True)
        db.session.commit()
        print("Tabela 'tenants' pronta.")

        for tenant_info in tenants_to_create:
            create_tenant_schema_and_tables(tenant_info)

        print("\nConfigurando usuário admin para o tenant 'alpha'...")
        db.session.execute(text('SET search_path TO alpha'))
        admin_user = db.session.query(Usuario).filter_by(login='admin').first()
        if not admin_user:
            admin_user = Usuario(login='admin', nome='Administrador Alpha', role='admin')
            admin_user.set_password('admin')
            db.session.add(admin_user)
            print("Usuário 'admin' criado para o tenant 'alpha'.")
        else:
            print("Usuário 'admin' já existe para o tenant 'alpha'.")

        db.session.commit()

    print("\\nConfiguração inicial do banco de dados concluída com sucesso!")

if __name__ == "__main__":
    cli()
