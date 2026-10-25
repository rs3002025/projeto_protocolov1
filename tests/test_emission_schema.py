"""Reproduz o índice único legado que impedia a assinatura no recebimento."""
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from emission_schema import upgrade_emission_protocol_index


def check_upgrade(engine):
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE emissoes_eletronicas (id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, protocolo_id INTEGER NOT NULL, versao INTEGER NOT NULL, pdf_sha256 VARCHAR(64), UNIQUE(tenant_id, protocolo_id, versao))'))
        connection.execute(text('CREATE UNIQUE INDEX ix_emissoes_eletronicas_protocolo_id ON emissoes_eletronicas (protocolo_id)'))
        connection.execute(text("INSERT INTO emissoes_eletronicas VALUES (1,1,17,1,'original-preservado')"))
    with engine.begin() as connection:
        upgrade_emission_protocol_index(connection)
        upgrade_emission_protocol_index(connection)
        index = next(i for i in inspect(connection).get_indexes('emissoes_eletronicas')
                     if i['name'] == 'ix_emissoes_eletronicas_protocolo_id')
        assert not index['unique']
        assert index['column_names'] == ['protocolo_id']
        connection.execute(text("INSERT INTO emissoes_eletronicas VALUES (2,1,17,2,'assinatura-responsavel')"))
        assert connection.execute(text('SELECT pdf_sha256 FROM emissoes_eletronicas WHERE id=1')).scalar_one() == 'original-preservado'
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO emissoes_eletronicas VALUES (3,1,17,2,'duplicada')"))
    with engine.begin() as connection:
        assert connection.execute(text('SELECT count(*) FROM emissoes_eletronicas')).scalar_one() == 2


def test_legacy_unique_index_becomes_lookup_without_losing_version_uniqueness():
    engine = create_engine('sqlite://')
    try:
        check_upgrade(engine)
    finally:
        engine.dispose()
