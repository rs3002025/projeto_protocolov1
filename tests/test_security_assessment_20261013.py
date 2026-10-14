"""Tentativas defensivas somente no SQLite temporário; nunca usar Railway."""
import pytest
import test_multitenancy as base
from app import app, db
from models import Protocolo


def setup_module():
    base.setup_module()


def teardown_module():
    base.teardown_module()


@pytest.mark.parametrize('payload', ["' OR '1'='1", "admin'--", "' UNION SELECT NULL--"])
def test_sql_login_cannot_authenticate(payload):
    client = app.test_client()
    response = client.post('/entrar/cliente-a', data={
        'organizacao': 'cliente-a', 'login': payload, 'senha': 'nao-valida'})
    assert response.status_code in (200, 429)
    with client.session_transaction() as session:
        assert not session.get('_user_id')
    assert client.get('/protocolo/1').status_code == 302
    with app.app_context():
        assert Protocolo.query.count() == 2


@pytest.mark.parametrize('field', ['nome', 'observacoes'])
def test_stored_html_remains_text(field):
    payload = '<img src=x onerror="alert(31337)">'
    with app.app_context():
        protocol = db.session.get(Protocolo, 1)
        original = getattr(protocol, field)
        setattr(protocol, field, payload)
        db.session.commit()
    try:
        client = app.test_client()
        base.login(client, 'cliente-a')
        response = client.get('/protocolo/1')
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert payload not in html
        assert '&lt;img' in html
    finally:
        with app.app_context():
            setattr(db.session.get(Protocolo, 1), field, original)
            db.session.commit()


def test_forged_cookie_does_not_open_protocol():
    client = app.test_client()
    client.set_cookie('session', 'eyJfdXNlcl9pZCI6IjEifQ.forged.signature')
    assert client.get('/protocolo/1').status_code == 302


@pytest.mark.parametrize('path', ['/static/../.env', '/static/%2e%2e/.env'])
def test_static_traversal_does_not_read_configuration(path):
    assert app.test_client().get(path).status_code == 404
