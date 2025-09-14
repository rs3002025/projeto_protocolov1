import sys
from flask.cli import FlaskGroup
from sqlalchemy import create_engine, text
from sqlalchemy.schema import CreateSchema
from app import create_app, db
from app.models import Tenant

# Adiciona o diretório app ao path para importação correta
# sys.path.append('app') # FlaskGroup deve lidar com isso

cli = FlaskGroup(create_app=create_app)

@cli.command("init-db")
def init_db():
    """Inicializa o banco de dados, cria schemas e tabelas para os tenants."""

    app = cli.create_app()
    engine = db.get_engine()

    tenants_to_create = [
        {'name': 'Cliente Alpha', 'client_code': 'alpha', 'schema_name': 'alpha'},
        {'name': 'Cliente Beta', 'client_code': 'beta', 'schema_name': 'beta'},
        {'name': 'Cliente Gamma', 'client_code': 'gamma', 'schema_name': 'gamma'},
        {'name': 'Cliente Delta', 'client_code': 'delta', 'schema_name': 'delta'},
        {'name': 'Cliente Epsilon', 'client_code': 'epsilon', 'schema_name': 'epsilon'},
    ]

    with app.app_context():
        # 1. Criar a tabela de tenants no schema public
        print("Criando tabela 'tenants' no schema 'public'...")
        # Força a criação apenas da tabela Tenant, que está no schema 'public'
        Tenant.__table__.create(bind=engine, checkfirst=True)
        print("Tabela 'tenants' criada com sucesso.")

        for tenant_info in tenants_to_create:
            schema_name = tenant_info['schema_name']

            # 2. Criar o schema para o tenant
            print(f"Criando schema '{schema_name}'...")
            with engine.connect() as connection:
                # Usar 'if_not_exists=True' na criação do schema
                if not connection.dialect.has_schema(connection, schema_name):
                    connection.execute(CreateSchema(schema_name))
                connection.commit()
            print(f"Schema '{schema_name}' criado ou já existente.")

            # 4. Criar todas as tabelas (exceto a de tenant) dentro do novo schema
            print(f"Criando tabelas para o schema '{schema_name}'...")

            # Copia os metadados, mas sem a tabela 'tenants'
            tenant_metadata = db.MetaData()
            for table in db.metadata.tables.values():
                if table.name != 'tenants':
                    table.tometadata(tenant_metadata, schema=schema_name)

            tenant_metadata.create_all(engine)
            print(f"Tabelas criadas com sucesso para o schema '{schema_name}'.")

            # 5. Adicionar o tenant na tabela 'tenants' no schema public
            tenant_entry = db.session.query(Tenant).filter_by(client_code=tenant_info['client_code']).first()
            if not tenant_entry:
                new_tenant = Tenant(
                    name=tenant_info['name'],
                    client_code=tenant_info['client_code'],
                    schema_name=tenant_info['schema_name']
                )
                db.session.add(new_tenant)
                print(f"Adicionando tenant '{tenant_info['name']}' à tabela de tenants.")

        db.session.commit()

    print("\\nConfiguração inicial do banco de dados concluída com sucesso!")

if __name__ == "__main__":
    cli()
