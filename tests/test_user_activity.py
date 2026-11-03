from datetime import timedelta
from unittest.mock import patch

import test_multitenancy as base
from app import app, db, bcrypt
from models import AtividadeUsuario, Usuario
from user_activity import active_counts, is_recent, record_activity, utcnow


def setup_module():
    base.setup_module()
    with app.app_context():
        db.session.add(Usuario(nome='Global', login='global-activity', tipo='admin',
            senha=bcrypt.generate_password_hash('senha-segura').decode(),
            is_platform_admin=True, status='ativo'))
        db.session.commit()


def teardown_module():
    base.teardown_module()


def global_client():
    client = app.test_client()
    result = client.post('/login', data={'login': 'global-activity', 'senha': 'senha-segura'})
    assert result.status_code == 302
    return client


def test_activity_is_exclusive_to_platform_even_with_tenant_selected():
    anonymous = app.test_client()
    assert anonymous.get('/plataforma/clientes/1/atividade').status_code == 302
    tenant_admin = app.test_client()
    base.login(tenant_admin, 'cliente-a')
    assert tenant_admin.get('/plataforma/clientes/1/atividade').status_code == 403
    assert tenant_admin.get('/plataforma/clientes/2/atividade').status_code == 403
    global_admin = global_client()
    assert global_admin.get('/plataforma/clientes/1/atividade').status_code == 200
    assert global_admin.post('/plataforma/cliente/2').status_code == 302
    assert global_admin.get('/plataforma/clientes/1/atividade').status_code == 200
    assert global_admin.get('/plataforma/clientes/987654/atividade').status_code == 404


def test_client_lists_are_separate_and_do_not_expose_credentials():
    with app.app_context():
        record_activity(1, 1)
        record_activity(2, 2)
    client = global_client()
    first = client.get('/plataforma/clientes/1/atividade')
    second = client.get('/plataforma/clientes/2/atividade')
    assert first.cache_control.no_store
    assert 'Ana A' in first.text and 'Bia B' not in first.text
    assert 'Bia B' in second.text and 'Ana A' not in second.text
    assert 'senha-segura' not in first.text
    assert 'global-activity' not in first.text
    assert 'Ver atividade dos usuários' in client.get('/plataforma').text


def test_one_row_per_user_throttled_and_inactive_accounts_excluded():
    now = utcnow()
    with app.app_context():
        AtividadeUsuario.query.delete()
        db.session.commit()
        record_activity(1, 1, now - timedelta(minutes=10))
        record_activity(1, 1, now - timedelta(minutes=10, seconds=-30))
        activity = db.session.get(AtividadeUsuario, 1)
        assert not is_recent(activity.ultimo_acesso_em, now)
        assert active_counts(now) == {}
        record_activity(1, 1, now)
        record_activity(2, 2, now)
        db.session.expire_all()
        assert AtividadeUsuario.query.count() == 2
        assert active_counts(now) == {1: 1, 2: 1}
        user = db.session.get(Usuario, 2)
        user.status = 'inativo'
        db.session.commit()
        assert active_counts(now) == {1: 1}
        user.status = 'ativo'
        db.session.commit()


def test_boundaries_and_future_clock():
    now = utcnow()
    assert is_recent(now - timedelta(minutes=5), now)
    assert not is_recent(now - timedelta(minutes=5, seconds=1), now)
    assert not is_recent(now + timedelta(seconds=1), now)


def test_navigation_recorded_but_assets_json_and_errors_do_not_refresh_activity():
    client = app.test_client()
    with patch('user_activity.record_activity') as record:
        base.login(client, 'cliente-a')
        assert record.called
        record.reset_mock()
        client.get('/static/script.js')
        client.get('/nao-existe-activity')
        client.get('/home', headers={'X-Requested-With': 'XMLHttpRequest'})
        assert not record.called
        client.get('/home')
        record.assert_called_once_with(1, 1)
        record.reset_mock()
        client.post('/admin/item/tipo/novo', data={'nome': 'Atividade QA'},
                    headers={'X-Requested-With': 'XMLHttpRequest'})
        record.assert_called_once_with(1, 1)


def test_activity_failure_does_not_break_navigation():
    from sqlalchemy.exc import OperationalError
    client = app.test_client()
    base.login(client, 'cliente-a')
    with patch('user_activity.record_activity', side_effect=OperationalError('private-activity-db-error', {}, Exception('private-activity-db-error'))):
        response = client.get('/home')
        assert response.status_code == 200
        assert 'private-activity-db-error' not in response.text
