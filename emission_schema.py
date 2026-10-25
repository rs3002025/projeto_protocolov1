"""Compatibilidade do índice legado com as evidências por versão."""
from sqlalchemy import inspect, text


def upgrade_emission_protocol_index(connection):
    # unique=True,index=True no modelo antigo gerava um índice, não uma
    # constraint com o nome protocolo_id_key. Preservar a chave por versão.
    name = 'ix_emissoes_eletronicas_protocolo_id'
    indexes = inspect(connection).get_indexes('emissoes_eletronicas')
    for index in indexes:
        if (index['name'] == name and index.get('unique')
                and index.get('column_names') == ['protocolo_id']
                and not index.get('duplicates_constraint')):
            connection.execute(text(f'DROP INDEX {name}'))
    connection.execute(text(f'CREATE INDEX IF NOT EXISTS {name} ON emissoes_eletronicas (protocolo_id)'))
