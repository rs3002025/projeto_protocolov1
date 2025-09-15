from sqlalchemy import text, event
from flask import g
from app import db

def set_tenant_schema_for_request(schema_name):
    """
    Define o search_path para o schema do tenant na sessão atual do DB.
    Esta função será chamada por um before_request handler.
    """
    try:
        if schema_name and schema_name.isalnum():
            # Armazena o schema no 'g' para que possa ser usado em toda a requisição
            g.schema = schema_name
        else:
            g.schema = 'public' # Fallback
    except Exception as e:
        # Em caso de erro, default para public para evitar falhas
        g.schema = 'public'

# Usar o evento 'before_cursor_execute' do SQLAlchemy é mais robusto
# do que fazer um SET search_path por requisição.
@event.listens_for(db.engine, "before_cursor_execute")
def set_schema_on_execute(conn, cursor, statement, parameters, context, executemany):
    """
    Define o search_path em cada execução de cursor.
    Pega o schema do objeto 'g' do Flask, que é thread-safe.
    """
    if 'schema' in g:
        # A forma mais segura de fazer isso, evitando SQL injection
        # e garantindo que o search_path seja o primeiro comando na transação.
        cursor.execute(f"SET search_path TO {g.schema}, public")
    else:
        cursor.execute("SET search_path TO public")
