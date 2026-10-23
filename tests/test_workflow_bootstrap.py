"""Atualização de bancos existentes sem acessar dados de nenhum ambiente."""
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = r'''
import os
from sqlalchemy import inspect, text
from app import app, db
from bootstrap_db import bootstrap
from models import (
    AcompanhamentoProtocolo, Lotacao, Movimentacao, Organizacao,
    Protocolo, ProvidenciaProtocolo, Usuario,
)

with app.app_context():
    assert db.engine.dialect.name == 'sqlite'
    db.create_all()
    for number, slug in ((1, 'prefeitura'), (2, 'outro-cliente')):
        org = Organizacao(id=number, nome=slug, slug=slug)
        user = Usuario(id=number, tenant_id=number, nome=slug, login=slug,
                       senha='fictitious-test-only', tipo='consulta')
        sector = Lotacao(id=number, tenant_id=number, nome=slug)
        protocol = Protocolo(id=number, tenant_id=number, numero='0001/2026',
                             nome=slug, status='EM ANÁLISE', responsavel=slug,
                             consulta_token='preserved-token-' + slug)
        db.session.add_all([org, user, sector, protocol])
    db.session.commit()
    for number in (1, 2):
        db.session.add(Movimentacao(
            id=number, tenant_id=number, protocolo_id=number,
            setor_destino_id=number, enviado_por_id=number,
            observacao='Movimentação preservada'))
    db.session.commit()
    db.session.remove()

    if os.environ['SCHEMA_FIXTURE'] == 'legacy':
        # Reproduz tabelas anteriores à mudança, preservando suas linhas.
        removed = {
            'protocolos': {'excluido_em', 'finalizado_em', 'resultado_final'},
            'movimentacoes': {'providencia_id', 'envio_token'},
            'despachos_protocolos': {'excluido_em', 'excluido_por_id', 'motivo_exclusao', 'assunto', 'conteudo_delta'},
        }
        with db.engine.begin() as connection:
            for table, columns in removed.items():
                keep = ', '.join('"' + c['name'] + '"' for c in
                                 inspect(connection).get_columns(table)
                                 if c['name'] not in columns)
                connection.execute(text(f'CREATE TABLE {table}_legacy AS SELECT {keep} FROM {table}'))
                connection.execute(text(f'DROP TABLE {table}'))
                connection.execute(text(f'ALTER TABLE {table}_legacy RENAME TO {table}'))
            connection.execute(text('DROP TABLE acompanhamentos_protocolos'))
            connection.execute(text('DROP TABLE providencias_protocolos'))

    bootstrap()
    bootstrap()  # Reiniciar o contêiner deve ser seguro.
    columns={c['name'] for c in inspect(db.engine).get_columns('despachos_protocolos')}
    assert {'excluido_em','excluido_por_id','motivo_exclusao','assunto','conteudo_delta'} <= columns
    for number, slug in ((1, 'prefeitura'), (2, 'outro-cliente')):
        protocol = db.session.get(Protocolo, number)
        assert protocol.tenant_id == number
        assert protocol.numero == '0001/2026'
        assert protocol.nome == slug
        assert protocol.consulta_token == 'preserved-token-' + slug
        assert protocol.responsavel_exibicao == slug
        assert protocol.resultado_final is None
        assert protocol.excluido_em is None and protocol.finalizado_em is None
        movement = db.session.get(Movimentacao, number)
        assert movement.tenant_id == number
        assert movement.observacao == 'Movimentação preservada'
        assert movement.providencia_id is None and movement.envio_token is None
        assert db.session.get(Usuario, number).senha == 'fictitious-test-only'

    action = ProvidenciaProtocolo(tenant_id=1, protocolo_id=1)
    db.session.add(action)
    db.session.flush()
    movement = db.session.get(Movimentacao, 1)
    movement.providencia_id = action.id
    movement.envio_token = 'test-movement-token'
    db.session.add(AcompanhamentoProtocolo(tenant_id=1, protocolo_id=1, usuario_id=1))
    db.session.commit()
    assert action.movimento_atual.id == 1
    assert 'Aguardando recebimento' in db.session.get(Protocolo, 1).responsavel_exibicao
    assert db.session.get(Protocolo, 2).responsavel_exibicao == 'outro-cliente'
    indexes = {index['name'] for index in inspect(db.engine).get_indexes('movimentacoes')}
    assert 'ix_movimentacoes_providencia_id' in indexes
    foreign_keys = inspect(db.engine).get_foreign_keys('movimentacoes')
    assert any(fk['constrained_columns'] == ['providencia_id'] and
               fk['referred_table'] == 'providencias_protocolos' for fk in foreign_keys)
'''


@pytest.mark.parametrize('schema', ['legacy', 'current'])
def test_bootstrap_preserves_existing_protocols_and_movements(tmp_path, schema):
    environment = os.environ.copy()
    environment.update(
        SECRET_KEY='isolated-workflow-migration-test',
        DATABASE_URL='sqlite:///' + str(tmp_path / 'migration.sqlite3'),
        DEFAULT_ORGANIZATION_SLUG='prefeitura',
        TENANT_SUBDOMAINS_ENABLED='false',
        SCHEMA_FIXTURE=schema,
    )
    environment.pop('BOOTSTRAP_ADMIN_PASSWORD', None)
    result = subprocess.run([sys.executable, '-c', SCRIPT], cwd=ROOT,
                            env=environment, text=True, capture_output=True,
                            timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
