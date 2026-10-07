"""Consulta administrativa: isolamento, dados mínimos e registro transacional."""
from pathlib import Path
from datetime import date
import test_multitenancy as base
from app import app, db, _admin_audit
from models import Servidor, HistoricoProtocolo


def setup_module():
    Path(base._test_directory.name).mkdir(exist_ok=True)
    base.setup_module()
    with app.app_context():
        db.session.add(Servidor(tenant_id=1, matricula='INCOMPLETO', nome='Pessoa incompleta'))
        db.session.add(Servidor(tenant_id=2, matricula='OUTRO-CLIENTE', nome='Pessoa de outro cliente'))
        db.session.commit()


def teardown_module():
    base.teardown_module()


def test_readiness_reports_missing_fields_without_crossing_clients():
    client = app.test_client()
    base.login(client, 'cliente-a')
    response = client.get('/admin/servidores/cadastro-portal?matricula=INCOMPLETO')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Dados incompletos' in body and 'CPF, data de nascimento, nome da mãe' in body
    assert 'Pessoa de outro cliente' not in body
    other = client.get('/admin/servidores/cadastro-portal?matricula=OUTRO-CLIENTE')
    assert 'Nenhum cadastro encontrado' in other.get_data(as_text=True)


def test_readiness_requires_login():
    assert app.test_client().get('/admin/servidores/cadastro-portal').status_code == 302


def test_blank_and_malformed_data_are_not_ready():
    server = Servidor(nome=' ', cpf='abc', nome_mae=' ', nascimento=None)
    assert server.pendencias_autocadastro == ['nome', 'CPF', 'data de nascimento', 'nome da mãe']
    server.nome, server.cpf = 'Pessoa', '01234567890'
    server.nome_mae, server.nascimento = 'Maria', date(1990, 1, 1)
    assert not server.pendencias_autocadastro


def test_admin_audit_does_not_commit_separately():
    client = app.test_client()
    base.login(client, 'cliente-a')
    with client:
        client.get('/admin/servidores/cadastro-portal')
        _admin_audit('TESTE_TRANSACAO', 'Operação administrativa de teste.')
        db.session.rollback()
        assert HistoricoProtocolo.query.filter_by(acao='TESTE_TRANSACAO').count() == 0

