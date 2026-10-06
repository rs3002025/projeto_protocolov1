"""Cadastro em etapas: perguntas sorteadas e isolamento da identificação."""
from datetime import date
from pathlib import Path
from unittest.mock import patch
import test_multitenancy as base
from app import app, db
from models import Organizacao, Servidor


def setup_module():
    Path(base._test_directory.name).mkdir(exist_ok=True)
    base.setup_module()
    with app.app_context():
        for tenant_id in (1, 2):
            db.session.get(Organizacao, tenant_id).portal_servidor_remoto_enabled = True
            db.session.add(Servidor(tenant_id=tenant_id, matricula='SORTEIO',
                nome='Pessoa Teste', cpf='01234567890', nascimento=date(1985, 5, 10),
                nome_mae='Maria Exemplo'))
        db.session.commit()


def teardown_module():
    base.teardown_module()


def payload():
    return dict(matricula='SORTEIO', nome='Pessoa Teste', cpf='01234567890',
        primeiro_nome_mae='Maria', ultimo_nome_mae='Exemplo', ano_nascimento='1985',
        mes_nascimento='05', dia_nascimento='10', telefone='88999999999',
        endereco='Rua Teste, 1', email='pessoa@example.test', senha='Teste123',
        confirmar_senha='Teste123')


def identify(client):
    with patch('app.secrets.choice', side_effect=lambda values: values[-1]):
        assert client.post('/portal/cliente-a/cadastre-se', data={
            'etapa': 'identificar', 'matricula': 'SORTEIO'}).status_code == 302


def test_cannot_skip_identification_or_send_email():
    client = app.test_client()
    with patch('app._send_account_email') as send:
        assert client.post('/portal/cliente-a/cadastre-se', data=payload()).status_code == 400
        send.assert_not_called()


def test_questions_follow_selected_variants_and_validate_answers():
    client = app.test_client()
    identify(client)
    page = client.get('/portal/cliente-a/cadastre-se').get_data(as_text=True)
    assert 'name="ultimo_nome_mae"' in page and 'name="dia_nascimento"' in page
    assert 'name="primeiro_nome_mae"' not in page and 'name="ano_nascimento"' not in page
    with patch('app._send_account_email') as send:
        assert client.post('/portal/cliente-a/cadastre-se', data={
            **payload(), 'ultimo_nome_mae': 'Outra'}).status_code == 400
        send.assert_not_called()
        assert client.post('/portal/cliente-a/cadastre-se', data=payload()).status_code == 302
        assert send.call_count == 1
    with client.session_transaction() as state:
        assert 'portal_identificacao' not in state
        assert state.get('portal_cadastro_id')
    repeat = app.test_client()
    identify(repeat)
    with patch('app._send_account_email') as send:
        assert repeat.post('/portal/cliente-a/cadastre-se', data=payload()).status_code == 429
        send.assert_not_called()


def test_expired_challenge_returns_to_identification():
    client = app.test_client()
    identify(client)
    with client.session_transaction() as state:
        challenge = dict(state['portal_identificacao'])
        challenge['expira'] = 0
        state['portal_identificacao'] = challenge
    with patch('app._send_account_email') as send:
        response = client.post('/portal/cliente-a/cadastre-se', data=payload())
        assert response.status_code == 400
        assert 'name="etapa" value="identificar"' in response.get_data(as_text=True)
        send.assert_not_called()


def test_challenge_cannot_cross_clients():
    client = app.test_client()
    identify(client)
    with patch('app._send_account_email') as send:
        assert client.post('/portal/cliente-b/cadastre-se', data=payload()).status_code == 400
        send.assert_not_called()

