from sqlalchemy.schema import CreateSchema
from ..extensions import db
from ..models import Tenant

def create_tenant_schema_and_tables(tenant_info):
    """
    Cria um novo schema de tenant e todas as tabelas necessárias dentro dele.
    Esta função é projetada para ser reutilizável.
    """
    schema_name = tenant_info.get('schema_name')
    if not schema_name:
        raise ValueError("O nome do schema é obrigatório.")

    engine = db.engine

    # 1. Criar o schema para o tenant
    print(f"Criando schema '{schema_name}'...")
    with engine.connect() as connection:
        if not connection.dialect.has_schema(connection, schema_name):
            connection.execute(CreateSchema(schema_name))
            connection.commit()
            print(f"Schema '{schema_name}' criado.")
        else:
            print(f"Schema '{schema_name}' já existente.")

    # 2. Criar todas as tabelas (exceto a de tenant) dentro do novo schema
    print(f"Criando tabelas para o schema '{schema_name}'...")

    # Lista de tabelas a serem criadas no schema do tenant
    tenant_tables = [table for table in db.metadata.tables.values() if table.name != 'tenants']

    # Usar schema_translate_map para direcionar a criação das tabelas
    with engine.connect().execution_options(schema_translate_map={None: schema_name}) as connection:
        db.metadata.create_all(bind=connection, tables=tenant_tables)
        # O commit será tratado pelo chamador para garantir a atomicidade.

    print(f"Tabelas criadas com sucesso para o schema '{schema_name}'.")

    # 3. Adicionar o tenant na tabela 'tenants' no schema public
    tenant_entry = db.session.query(Tenant).filter_by(client_code=tenant_info['client_code']).first()
    if not tenant_entry:
        new_tenant = Tenant(
            name=tenant_info['name'],
            client_code=tenant_info['client_code'],
            schema_name=tenant_info['schema_name']
        )
        db.session.add(new_tenant)
        db.session.commit()
        print(f"Adicionando tenant '{tenant_info['name']}' à tabela de tenants.")
        return new_tenant
    else:
        print(f"Tenant com client_code '{tenant_info['client_code']}' já existe.")
        return tenant_entry
