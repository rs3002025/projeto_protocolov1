"""Regressões do cadastro, senha inicial, despacho e avisos por responsável."""
import io
from unittest.mock import patch
import pytest
from flask import template_rendered
from pypdf import PdfReader
import test_authorizations as auth
from app import app, bcrypt, db, verify_audit_chain
from models import (Usuario, Organizacao, DespachoProtocolo, AutorizacaoProtocolo,
                    NotificacaoAutorizacao, Protocolo, Servidor, PortalSessao)

setup_function = auth.setup_function
teardown_function = auth.teardown_function


def test_pending_authorization_filter_matches_list_report_export_and_stored_status_is_unchanged():
    from openpyxl import load_workbook
    auth.solicit()
    c=auth.client()
    with app.app_context():
        p=Protocolo.query.filter_by(tenant_id=1).one()
        number=p.numero
        assert p.status=='RECEBIDO'
    params={'numero':number,'status':'AGUARDANDO AUTORIZAÇÃO'}
    for path in ('/protocolos','/relatorios'):
        response=c.get(path,query_string=params)
        assert response.status_code==200
        body=response.get_data(as_text=True)
        assert number in body and 'Nenhum protocolo encontrado.' not in body
        assert '<option' in body and 'AGUARDANDO AUTORIZAÇÃO' in body
    response=c.get('/protocolos/backup/excel',query_string=params)
    assert response.status_code==200
    rows=list(load_workbook(io.BytesIO(response.data),read_only=True).active.values)
    assert len(rows)==2 and number in rows[1]
    response=c.get('/relatorios',query_string={'numero':number,'status':'RECEBIDO'})
    assert 'Nenhum protocolo encontrado.' in response.get_data(as_text=True)
    with app.app_context():
        assert Protocolo.query.filter_by(tenant_id=1).one().status=='RECEBIDO'
        db.session.get(Organizacao,1).autorizacao_protocolos_enabled=False
        db.session.commit()
    body=c.get('/relatorios').get_data(as_text=True)
    assert 'value="AGUARDANDO AUTORIZAÇÃO"' not in body


def test_default_password_cannot_be_overridden_and_reset_revokes_existing_session():
    admin = auth.client()
    data = dict(nome_completo='Pessoa Nova', cargo='Secretário de Administração', login='novo',
                email='novo@example.test', tipo='tramitador', lotacao_id='1', servidor_id='0', senha='Ignorada-2026')
    assert admin.post('/admin/usuarios/novo', data=data).status_code == 302
    with app.app_context():
        user = Usuario.query.filter_by(login='novo').one()
        uid = user.id
        assert user.cargo == 'Secretário de Administração'
        assert bcrypt.check_password_hash(user.senha, 'muni1234') and user.deve_trocar_senha
        assert not bcrypt.check_password_hash(user.senha, 'Ignorada-2026')
    person = app.test_client()
    assert person.post('/entrar/cliente-a', data=dict(login='novo', senha='muni1234')).status_code == 302
    assert '/minha-conta/trocar-senha' in person.get('/home').location
    bad = person.post('/minha-conta/trocar-senha', data=dict(senha_atual='muni1234', senha_nova='muni1234', confirmar_senha='muni1234'))
    assert bad.status_code == 200
    with app.app_context(): assert db.session.get(Usuario, uid).deve_trocar_senha
    assert person.post('/minha-conta/trocar-senha', data=dict(senha_atual='muni1234', senha_nova='NovaSenha2026', confirmar_senha='NovaSenha2026')).status_code == 302
    assert person.get('/home').status_code == 200
    assert admin.post(f'/admin/usuarios/{uid}/restaurar-senha', data={'confirmar':'1'}).status_code == 302
    assert person.get('/home').status_code == 302  # sessão anterior invalidada
    fresh = app.test_client()
    fresh.post('/entrar/cliente-a', data=dict(login='novo', senha='muni1234'))
    assert '/minha-conta/trocar-senha' in fresh.get('/home').location
    with app.app_context(): assert verify_audit_chain(1)[0]


def test_password_reset_requires_admin_confirmation_and_same_tenant():
    _, uid = auth.ids()
    assert auth.client('tramita').post(f'/admin/usuarios/{uid}/restaurar-senha', data={'confirmar':'1'}).status_code == 302
    assert auth.client().post(f'/admin/usuarios/{uid}/restaurar-senha', data={}).status_code == 400
    assert auth.client(tenant='cliente-b').post(f'/admin/usuarios/{uid}/restaurar-senha', data={'confirmar':'1'}).status_code == 404
    admin = auth.client()
    app.config['WTF_CSRF_ENABLED'] = True
    try:
        assert admin.post(f'/admin/usuarios/{uid}/restaurar-senha', data={'confirmar':'1'}).status_code == 400
    finally: app.config['WTF_CSRF_ENABLED'] = False


def test_cargo_optional_edit_and_authorization_is_a_standard_numbered_dispatch():
    admin = auth.client()
    pid, uid = auth.ids()
    assert admin.post(f'/admin/usuarios/{uid}/editar', data=dict(nome_completo='Pessoa Autorizadora',
        email='cargo@example.test', cargo='Secretário de Administração', tipo='autorizador', lotacao_id='1', servidor_id='0')).status_code == 302
    rid = auth.solicit(admin)
    assert auth.client('autoriza').post(f'/autorizacoes/{rid}/decidir', data={'decisao':'AUTORIZADO'}).status_code == 302
    with app.app_context():
        row = db.session.get(AutorizacaoProtocolo,rid)
        dispatch = row.despacho
        did = dispatch.id
        assert dispatch.numero == 1 and dispatch.autor_cargo == 'Secretário de Administração'
        assert dispatch.file_hash == row.documento.file_hash
        pdf = row.documento.file_data
        user = db.session.get(Usuario,uid); user.cargo = 'Cargo posterior'; db.session.commit()
        assert dispatch.autor_cargo == 'Secretário de Administração'
        content = ' '.join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
        assert 'DESPACHO 001' in content and 'Secretário de Administração' in content
        assert 'o prosseguimento do Protocolo' in content
    html = admin.get(f'/protocolo/{pid}').get_data(as_text=True)
    assert f'id="despacho-{did}"' in html and 'Autorização do prosseguimento' in html
    assert admin.get(f'/protocolo/{pid}/despachos/{did}/pdf').data == pdf
    assert admin.post(f'/protocolo/{pid}/despachos/{did}/excluir', data={'confirmar_exclusao':'1'}).status_code == 409


def test_dashboard_waiting_queue_and_decisions_only_notify_responsible():
    admin = auth.client(); rid = auth.solicit(admin)
    contexts=[]
    def capture(sender, template, context, **kw):
        if template.name == 'home.html': contexts.append(context['workbench'])
    with template_rendered.connected_to(capture,app):
        assert admin.get('/home?fila=autorizacao').status_code == 200
    wb = contexts[-1]
    assert wb['counts']['autorizacao'] == 1 and wb['counts']['analisar'] == 0
    assert any(d['label']=='Aguardando Autorização' for d in wb['distribution'])
    assert wb['rows'][0]['action'] == 'Consultar autorização'
    with patch('protocol_authorizations.render_authorization_pdf', return_value=b'%PDF-test'):
        c=auth.client('autoriza')
        c.post(f'/autorizacoes/{rid}/decidir',data={'decisao':'AUTORIZADO'})
        c.post(f'/autorizacoes/{rid}/decidir',data={'decisao':'AUTORIZADO'})
    with app.app_context():
        notes=NotificacaoAutorizacao.query.all()
        assert len(notes)==1
        nid=notes[0].id
        assert notes[0].usuario_id==Usuario.query.filter_by(tenant_id=1,login='admin').one().id
    assert 'Decisões dos seus protocolos' in admin.get('/home').get_data(as_text=True)
    assert 'Decisões dos seus protocolos' not in auth.client('tramita').get('/home').get_data(as_text=True)
    assert auth.client('tramita').post(f'/autorizacoes/notificacoes/{nid}/ler').status_code == 404
    assert admin.post(f'/autorizacoes/notificacoes/{nid}/ler').status_code==302
    assert 'Decisões dos seus protocolos' not in admin.get('/home').get_data(as_text=True)


def test_portal_reset_forces_password_change_before_access_and_revokes_sessions():
    from datetime import date
    with app.app_context():
        org=db.session.get(Organizacao,1); org.portal_servidor_remoto_enabled=True
        server=Servidor(tenant_id=1,nome='Servidor Teste',matricula='12345',cpf='12345678901',nascimento=date(1990,1,1),nome_mae='Mãe Teste')
        db.session.add(server);db.session.flush()
        user=Usuario(tenant_id=1,nome='Servidor',login='portal-novo',tipo='requerente',status='ativo',servidor_id=server.id,
            senha=bcrypt.generate_password_hash('AntigaSenha2026').decode())
        db.session.add(user);db.session.commit();uid=user.id
    old=app.test_client();old.post('/portal/cliente-a/entrar',data={'login':'portal-novo','senha':'AntigaSenha2026'})
    assert auth.client().post(f'/admin/usuarios/{uid}/restaurar-senha',data={'confirmar':'1'}).status_code==302
    fresh=app.test_client();fresh.post('/portal/cliente-a/entrar',data={'login':'portal-novo','senha':'muni1234'})
    assert '/minha-conta/trocar-senha' in fresh.get('/portal').location
    page=fresh.get('/minha-conta/trocar-senha');assert page.status_code==200 and 'Portal do Servidor' in page.get_data(as_text=True)
    assert fresh.post('/minha-conta/trocar-senha',data={'senha_atual':'muni1234','senha_nova':'NovaSenha2026','confirmar_senha':'NovaSenha2026'}).status_code==302
    with app.app_context(): assert not db.session.get(Usuario,uid).deve_trocar_senha
    assert old.get('/portal').status_code==302


def test_legacy_decision_backfill_preserves_pdf_and_is_idempotent():
    from protocol_authorizations import backfill_decision_dispatches
    rid=auth.solicit()
    with patch('protocol_authorizations.render_authorization_pdf',return_value=b'%PDF-original-preservado'):
        auth.client('autoriza').post(f'/autorizacoes/{rid}/decidir',data={'decisao':'NAO_AUTORIZADO'})
    with app.app_context():
        row=db.session.get(AutorizacaoProtocolo,rid)
        original=row.despacho; row.despacho=None;db.session.flush();db.session.delete(original);db.session.commit()
        count=NotificacaoAutorizacao.query.count()
        backfill_decision_dispatches();backfill_decision_dispatches()
        assert DespachoProtocolo.query.count()==1
        assert row.despacho.file_data==b'%PDF-original-preservado'
        assert row.despacho.file_hash==row.documento.file_hash
        assert NotificacaoAutorizacao.query.count()==count
        assert verify_audit_chain(1)[0]


def test_parallel_responsibles_receive_one_notification_each_without_followers():
    from datetime import datetime, timezone
    from models import ProvidenciaProtocolo, Movimentacao, AcompanhamentoProtocolo
    pid,uid=auth.ids()
    with app.app_context():
        p=db.session.get(Protocolo,pid)
        owners=Usuario.query.filter(Usuario.tenant_id==1,Usuario.login.in_(['admin','tramita'])).all()
        expected={u.id for u in owners}
        for owner in owners:
            participation=ProvidenciaProtocolo(tenant_id=1,protocolo_id=pid)
            db.session.add(participation);db.session.flush()
            db.session.add(Movimentacao(tenant_id=1,protocolo_id=pid,providencia_id=participation.id,setor_destino_id=1,
                enviado_por_id=owner.id,recebido_por_id=owner.id,recebido_em=datetime.now(timezone.utc)))
        observer=Usuario.query.filter_by(login='outro').one()
        db.session.add(AcompanhamentoProtocolo(tenant_id=1,protocolo_id=pid,usuario_id=observer.id))
        db.session.commit()
    rid=auth.solicit()
    with patch('protocol_authorizations.render_authorization_pdf',return_value=b'%PDF-paralelo'):
        assert auth.client('autoriza').post(f'/autorizacoes/{rid}/decidir',data={'decisao':'AUTORIZADO'}).status_code==302
    with app.app_context():
        assert {n.usuario_id for n in NotificacaoAutorizacao.query.all()}==expected
