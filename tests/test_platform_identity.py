from pathlib import Path
import test_multitenancy as base
from app import app, db, bcrypt
from models import Usuario, Organizacao


def setup_module():
    Path(base._test_directory.name).mkdir(exist_ok=True)
    base.setup_module()
    with app.app_context():
        db.session.add(Usuario(tenant_id=None, nome='Global', login='global',
            senha=bcrypt.generate_password_hash('senha-segura').decode(),
            tipo='admin', is_platform_admin=True, status='ativo'))
        db.session.commit()


def teardown_module():
    base.teardown_module()


def test_global_login_without_client_and_explicit_context():
    client = app.test_client()
    assert 'floatingOrganization' not in client.get('/login').get_data(as_text=True)
    result = client.post('/login', data={'login': 'global', 'senha': 'senha-segura'})
    assert result.headers['Location'] == '/plataforma'
    assert client.get('/protocolos').headers['Location'] == '/plataforma'
    assert client.post('/plataforma/cliente/2').headers['Location'] == '/home'
    assert 'Dado exclusivo B' in client.get('/protocolos').get_data(as_text=True)
    with app.app_context():
        user = Usuario.query.filter_by(login='global').one()
        assert user.tenant_id is None and user.is_active
        db.session.get(Organizacao, 1).ativo = False
        db.session.commit()
        assert user.is_active


def test_client_account_cannot_use_global_login():
    client = app.test_client()
    assert client.post('/login', data={'login': 'admin', 'senha': 'senha-segura'}).status_code == 200
    assert client.get('/plataforma').status_code == 302
