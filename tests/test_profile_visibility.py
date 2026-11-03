"""Conta própria e privacidade externa, sempre em SQLite descartável."""
from datetime import date
import hashlib
import test_multitenancy as base
from app import app, db, bcrypt, verify_audit_chain
from models import Organizacao, Usuario, Servidor, Protocolo, HistoricoProtocolo, Anexo


def setup_function():
    base.setup_module()
    with app.app_context():
        org = db.session.get(Organizacao, 1)
        org.portal_servidor_remoto_enabled = True
        server = Servidor(tenant_id=1, matricula='SERVER', nome='Servidor Teste')
        db.session.add(server); db.session.flush()
        pwd = bcrypt.generate_password_hash('senha-segura').decode()
        portal = Usuario(tenant_id=1, nome='Servidor', login='SERVER', tipo='requerente',
                         senha=pwd, servidor_id=server.id, status='ativo')
        worker = Usuario(tenant_id=1, nome='Tramitador', nome_completo='Tramitador Teste',
                         login='tramita', tipo='tramitador', senha=pwd, status='ativo')
        db.session.add_all([portal, worker]); db.session.flush()
        p = Protocolo.query.filter_by(tenant_id=1).one()
        p.requerente_servidor_id = server.id
        p.setor_atual_id = 2
        db.session.add(HistoricoProtocolo(tenant_id=1, protocolo_id=p.id, acao='TRAMITACAO',
            status='EM TRAMITAÇÃO', observacao='HISTORICO_INTERNO_SIGILOSO'))
        for name, owner in [('proprio.txt',portal.id), ('interno.txt',1)]:
            data = b'arquivo de teste'
            db.session.add(Anexo(tenant_id=1, protocolo_id=p.id, file_name=name,
                storage_path=name, file_size=len(data), file_hash=hashlib.sha256(data).hexdigest(),
                mime_type='text/plain', file_data=data, enviado_por_id=owner))
        db.session.commit()


def teardown_function():
    base.teardown_module()


def internal(login='admin', tenant='cliente-a'):
    client=app.test_client()
    assert client.post('/entrar/'+tenant,data={'login':login,'senha':'senha-segura'}).status_code==302
    return client


def portal():
    client=app.test_client()
    assert client.post('/portal/cliente-a/entrar',data={'login':'SERVER','senha':'senha-segura'}).status_code==302
    return client


def test_self_service_is_available_without_management_and_ignores_privilege_fields():
    client=internal('tramita')
    assert 'Minha conta' in client.get('/minha-conta').get_data(as_text=True)
    assert 'Minha conta' in client.get('/home').get_data(as_text=True)
    r=client.post('/minha-conta',data=dict(nome_completo='Nome Atualizado',email='teste@example.test',
        telefone='88999999999',endereco='Rua Exemplo',tipo='admin',tenant_id=2,login='admin'))
    assert r.status_code==302
    with app.app_context():
        u=Usuario.query.filter_by(login='tramita').one()
        assert (u.nome_completo,u.email,u.tipo,u.tenant_id)==('Nome Atualizado','teste@example.test','tramitador',1)
        assert verify_audit_chain(1)[0]


def test_invalid_profile_preserves_previous_data_and_requires_login():
    assert app.test_client().get('/minha-conta').status_code==302
    c=internal('consulta')
    assert c.post('/minha-conta',data=dict(nome_completo='Nome Inválido',email='invalido')).status_code==200
    with app.app_context():
        assert Usuario.query.filter_by(login='consulta').one().nome_completo=='Cris Consulta'


def test_voluntary_password_change_revokes_old_sessions_and_never_routes_worker_to_pin():
    first=internal('tramita'); old=internal('tramita')
    r=first.post('/minha-conta/trocar-senha',data=dict(senha_atual='senha-segura',senha_nova='Nova-Senha-2026',confirmar_senha='Nova-Senha-2026'))
    assert r.status_code==302 and r.location.endswith('/minha-conta')
    assert first.get('/minha-conta').status_code==200
    assert old.get('/minha-conta').status_code==302
    assert app.test_client().post('/entrar/cliente-a',data={'login':'tramita','senha':'senha-segura'}).status_code==200
    assert app.test_client().post('/entrar/cliente-a',data={'login':'tramita','senha':'Nova-Senha-2026'}).status_code==302


def test_initial_password_change_for_worker_reaches_home():
    with app.app_context():
        Usuario.query.filter_by(login='tramita').one().deve_trocar_senha=True
        db.session.commit()
    c=internal('tramita')
    assert c.get('/minha-conta').location.endswith('/minha-conta/trocar-senha')
    r=c.post('/minha-conta/trocar-senha',data=dict(senha_atual='senha-segura',senha_nova='Nova-Senha-2026',confirmar_senha='Nova-Senha-2026'))
    assert r.status_code==302 and r.location.endswith('/home')


def test_settings_are_independent_tenant_scoped_validated_and_admin_only():
    c=internal()
    assert c.post('/admin/visibilidade-servidor',data=dict(consulta_publica_tramitacao_enabled='status',portal_tramitacao_enabled='tramitacao')).status_code==302
    with app.app_context():
        a=db.session.get(Organizacao,1); b=db.session.get(Organizacao,2)
        assert not a.consulta_publica_tramitacao_enabled and a.portal_tramitacao_enabled
        assert b.consulta_publica_tramitacao_enabled and b.portal_tramitacao_enabled
        assert verify_audit_chain(1)[0]
    assert c.post('/admin/visibilidade-servidor',data=dict(consulta_publica_tramitacao_enabled='invalido',portal_tramitacao_enabled='status')).status_code==400
    denied=internal('tramita').post('/admin/visibilidade-servidor',data={})
    assert denied.status_code==302 and denied.location.endswith('/home')
    with app.app_context():
        assert db.session.get(Organizacao,1).portal_tramitacao_enabled


def test_public_tracking_hides_history_and_location_but_keeps_authentication():
    with app.app_context():
        org=db.session.get(Organizacao,1); org.consulta_publica_tramitacao_enabled=False
        p=Protocolo.query.filter_by(tenant_id=1).one(); token=p.consulta_token
        db.session.commit()
    c=app.test_client()
    body=c.post('/consulta/'+token,data={'matricula':'MAT-A'}).get_data(as_text=True)
    assert '0001/2026' in body and 'Situação' in body
    assert 'Andamentos' not in body and 'Localização atual' not in body and 'Jurídico' not in body
    assert '0001/2026' not in c.post('/consulta/'+token,data={'matricula':'errada'}).get_data(as_text=True)
    with app.app_context():
        db.session.get(Organizacao,1).consulta_publica_tramitacao_enabled=True; db.session.commit()
    body=c.post('/consulta/'+token,data={'matricula':'MAT-A'}).get_data(as_text=True)
    assert 'Andamentos' in body and 'Localização atual' in body


def test_portal_status_only_hides_internal_history_and_blocks_internal_attachment_download():
    with app.app_context():
        db.session.get(Organizacao,1).portal_tramitacao_enabled=False
        p=Protocolo.query.filter_by(tenant_id=1).one(); pid=p.id
        aid=Anexo.query.filter_by(file_name='interno.txt').one().id
        own=Anexo.query.filter_by(file_name='proprio.txt').one().id
        db.session.commit()
    c=portal()
    from flask import url_for
    with app.test_request_context(): path=url_for('portal_detalhe',protocolo_id=pid)
    response=c.get(path); assert response.status_code==200
    body=response.get_data(as_text=True)
    assert 'Situação' in body and 'HISTORICO_INTERNO_SIGILOSO' not in body
    assert 'proprio.txt' in body and 'interno.txt' not in body
    assert c.get(f'/anexo/{aid}/download').status_code==404
    assert c.get(f'/anexo/{own}/download').status_code==200
    with app.app_context():
        db.session.get(Organizacao,1).portal_tramitacao_enabled=True; db.session.commit()
    body=c.get(path).get_data(as_text=True)
    assert 'HISTORICO_INTERNO_SIGILOSO' in body and 'interno.txt' in body


def test_on_demand_pdf_applies_portal_attachment_visibility_without_restricting_internal_pdf():
    import sys
    from types import SimpleNamespace
    from unittest.mock import patch
    with app.app_context():
        db.session.get(Organizacao,1).portal_tramitacao_enabled=False
        pid=Protocolo.query.filter_by(tenant_id=1).one().id
        db.session.commit()
    class CapturePdf:
        def __init__(self,*args,**kwargs): self.html=kwargs['string']
        def write_pdf(self): return self.html.encode('utf-8')
    with patch.dict(sys.modules,{'weasyprint':SimpleNamespace(HTML=CapturePdf)}):
        c=portal()
        response=c.get(f'/protocolo/{pid}/pdf')
        assert response.status_code==200
        assert b'proprio.txt' in response.data and b'interno.txt' not in response.data
        response=internal().get(f'/protocolo/{pid}/pdf')
        assert response.status_code==200 and b'interno.txt' in response.data
        with app.app_context():
            db.session.get(Organizacao,1).portal_tramitacao_enabled=True
            db.session.commit()
        assert b'interno.txt' in c.get(f'/protocolo/{pid}/pdf').data


def test_csrf_remains_required_for_profile_and_visibility():
    c=internal()
    app.config['WTF_CSRF_ENABLED']=True
    try:
        assert c.post('/minha-conta',data={'nome_completo':'Outro'}).status_code==400
        assert c.post('/admin/visibilidade-servidor',data={}).status_code==400
    finally:
        app.config['WTF_CSRF_ENABLED']=False
