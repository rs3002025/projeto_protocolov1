"""Recebimentos de entrada sem PIN: dados fictícios em SQLite isolado."""
from pathlib import Path
import pytest
import test_multitenancy as base
from app import app, db, verify_audit_chain
from models import Organizacao, Protocolo, Usuario, HistoricoProtocolo, Servidor, Lotacao
from protocol_receipts import automatic_portal_receipt, receive_pending_without_signature


@pytest.fixture
def fixture():
    Path(base._test_directory.name).mkdir(exist_ok=True)
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.app_context():
        assert db.engine.dialect.name == 'sqlite'
        db.drop_all(); db.create_all()
        a = Organizacao(id=1, nome='Fictício A', slug='prefeitura', emissao_eletronica_protocolista_enabled=False)
        b = Organizacao(id=2, nome='Fictício B', slug='b', emissao_eletronica_protocolista_enabled=True)
        sector = Lotacao(id=1, tenant_id=1, nome='Protocolo fictício')
        admin = Usuario(id=1, tenant_id=1, nome='Admin fictício', login='admin', tipo='admin',
            senha='fictitious-not-a-real-credential', lotacao_id=1)
        global_admin = Usuario(id=2, nome='Global fictício', login='global', tipo='admin',
            senha='fictitious-not-a-real-credential', is_platform_admin=True)
        server = Servidor(id=1, tenant_id=1, nome='Pessoa fictícia', matricula='TEST')
        db.session.add_all([a, b, sector, admin, global_admin, server]); db.session.commit()
        identities = {'admin': admin.get_id(), 'global': global_admin.get_id()}
    yield identities
    with app.app_context():
        db.session.remove(); db.drop_all(); db.engine.dispose()


def request(tenant=1, number='0001/2026', status='AGUARDANDO RECEBIMENTO'):
    p = Protocolo(tenant_id=tenant, numero=number, nome='Pessoa fictícia', status=status,
        modalidade_abertura='remota_requerente', requerente_servidor_id=1 if tenant == 1 else None)
    db.session.add(p); db.session.flush()
    return p


def login(identities, role='admin'):
    client = app.test_client()
    with client.session_transaction() as s:
        s['_user_id'], s['_fresh'] = identities[role], True
    return client


def test_automatic_receipt_is_system_action_not_signature_or_human_receipt(fixture):
    with app.app_context():
        p = request()
        assert automatic_portal_receipt(p, db.session.get(Organizacao, 1))
        assert not automatic_portal_receipt(p, db.session.get(Organizacao, 1))
        db.session.commit()
        assert p.status == 'RECEBIDO' and not p.aguardando_recebimento_inicial
        assert p.responsavel is None and p.emitido_por_usuario_id is None
        assert p.responsavel_exibicao == 'Equipe de protocolo'
        h = HistoricoProtocolo.query.one()
        assert h.usuario_id is None and h.responsavel == 'Sistema'
        assert h.acao == 'RECEBIMENTO_AUTOMATICO'
        assert not p.emissoes_eletronicas
        assert verify_audit_chain(1)[0]


def test_existing_pending_only_without_signature_and_bootstrap_is_idempotent(fixture):
    from bootstrap_db import bootstrap
    with app.app_context():
        p = request()
        signed = request(2)
        closed = request(number='0002/2026', status='CONCLUÍDO')
        excluded = request(number='0003/2026'); from datetime import datetime
        excluded.excluido_em = datetime.now()
        ids = [p.id, signed.id, closed.id, excluded.id]
        db.session.commit()
    bootstrap(); bootstrap()
    with app.app_context():
        p, signed, closed, excluded = [db.session.get(Protocolo, i) for i in ids]
        assert p.status == 'RECEBIDO'
        assert signed.status == 'AGUARDANDO RECEBIMENTO' and signed.aguardando_recebimento_inicial
        assert closed.status == 'CONCLUÍDO' and excluded.status == 'AGUARDANDO RECEBIMENTO'
        assert HistoricoProtocolo.query.filter_by(acao='RECEBIMENTO_AUTOMATICO').count() == 1
        assert verify_audit_chain(1)[0]


def test_enabling_signature_does_not_reopen_received_and_disabling_receives_pending(fixture):
    with app.app_context():
        p = request(2); pid = p.id; db.session.commit()
        assert not automatic_portal_receipt(p, db.session.get(Organizacao, 2))
    client = login(fixture, 'global')
    assert client.post('/plataforma/cliente/2/capacidades', data={}).status_code == 302
    with app.app_context():
        p = db.session.get(Protocolo, pid)
        assert p.status == 'RECEBIDO' and p.recebido_automaticamente
    client.post('/plataforma/cliente/2/capacidades', data={'emissao_eletronica_protocolista_enabled': 'on'})
    with app.app_context():
        assert not db.session.get(Protocolo, pid).aguardando_recebimento_inicial
        assert HistoricoProtocolo.query.filter_by(acao='RECEBIMENTO_AUTOMATICO').count() == 1
        assert verify_audit_chain(2)[0]


def test_documents_and_staff_ownership_after_automatic_receipt(fixture):
    with app.app_context():
        p = request(); automatic_portal_receipt(p, db.session.get(Organizacao, 1))
        pid = p.id; db.session.commit()
    client = login(fixture)
    pending_page = client.get('/pendencias-recebimento').get_data(as_text=True)
    assert f'/protocolo/{pid}' not in pending_page
    detail = client.get(f'/protocolo/{pid}').get_data(as_text=True)
    assert 'Receber requerimento</button>' not in detail and 'Equipe de protocolo' in detail
    assert client.post('/protocolos/atualizar', json={'protocoloId': pid, 'novoStatus': 'EM ANÁLISE'}).status_code == 200
    assert client.post(f'/protocolo/{pid}/solicitar-complemento', data={'motivo': 'Envie a certidão funcional.'}).status_code == 302
    with app.app_context():
        p = db.session.get(Protocolo, pid)
        assert p.status == 'PENDENTE DE DOCUMENTO' and p.responsavel == 'admin' and p.setor_atual_id == 1
    assert client.post('/protocolos/atualizar', json={'protocoloId': pid, 'novoStatus': 'EM ANÁLISE'}).status_code == 409
    assert client.post(f'/protocolo/{pid}/finalizar').status_code == 409
    with app.app_context():
        p = db.session.get(Protocolo, pid); p.status = 'CONCLUÍDO'; db.session.commit()
    assert client.post(f'/protocolo/{pid}/solicitar-complemento', data={'motivo': 'Outra certidão funcional.'}).status_code == 409
