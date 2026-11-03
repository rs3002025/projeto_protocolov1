"""Autorizações nominais sem movimentação de custódia, em banco descartável."""
import io
import json
from datetime import datetime, timezone
from unittest.mock import patch
from urllib.parse import urlsplit

import pytest
from sqlalchemy import text
from PIL import Image
from pypdf import PdfReader
import test_multitenancy as base
from app import app, db, bcrypt, verify_audit_chain
from models import (AutorizacaoProtocolo, Anexo, DespachoProtocolo, HistoricoProtocolo,
                    Lotacao, Organizacao, Protocolo, Usuario)


def setup_function():
    base.setup_module()
    with app.app_context():
        a=db.session.get(Organizacao,1); a.autorizacao_protocolos_enabled=True
        pwd=bcrypt.generate_password_hash('senha-segura').decode()
        db.session.add_all([
            Usuario(tenant_id=1,nome='Secretário',nome_completo='Pessoa Autorizadora',login='autoriza',
                senha=pwd,tipo='autorizador',status='ativo'),
            Usuario(tenant_id=1,nome='Outro',login='outro',senha=pwd,tipo='autorizador',status='ativo'),
            Usuario(tenant_id=1,nome='Tramitador',login='tramita',senha=pwd,tipo='tramitador',status='ativo',pode_autorizar=True),
            Usuario(tenant_id=2,nome='Estrangeiro',login='fora',senha=pwd,tipo='autorizador',status='ativo'),
            Usuario(tenant_id=None,nome='Global',login='global',senha=pwd,tipo='admin',status='ativo',is_platform_admin=True),
        ])
        p=Protocolo.query.filter_by(tenant_id=1).one(); p.responsavel='admin'; p.setor_atual_id=1;p.status='RECEBIDO'
        db.session.commit()


def teardown_function():
    base.teardown_module()


def client(login='admin',tenant='cliente-a'):
    c=app.test_client()
    path='/login' if login=='global' else '/entrar/'+tenant
    assert c.post(path,data={'login':login,'senha':'senha-segura'}).status_code==302
    return c


def ids():
    with app.app_context():
        return (Protocolo.query.filter_by(tenant_id=1).one().id,
                Usuario.query.filter_by(login='autoriza').one().id)


def solicit(c=None,token='token-de-teste-123456789012345'):
    pid,uid=ids(); c=c or client()
    response=c.post(f'/protocolo/{pid}/solicitar-autorizacao',data={'autorizador_id':uid,'envio_token':token})
    assert response.status_code==302, response.get_data(as_text=True)
    with app.app_context():return AutorizacaoProtocolo.query.filter_by(envio_token=token).one().id


def png():
    out=io.BytesIO();Image.new('RGB',(3,3),'white').save(out,format='PNG');out.seek(0);return out


def test_request_has_no_description_and_keeps_custody_and_prevents_duplicates():
    c=client(); rid=solicit(c);pid,_=ids()
    assert solicit(c)==rid
    assert c.post(f'/protocolo/{pid}/solicitar-autorizacao',data={'autorizador_id':ids()[1],'envio_token':'outro-token-1234567890123456'}).status_code==409
    with app.app_context():
        p=db.session.get(Protocolo,pid)
        assert (p.responsavel,p.setor_atual_id,p.status)==('admin',1,'RECEBIDO')
        assert p.status_exibicao=='AGUARDANDO AUTORIZAÇÃO'
        assert not p.movimentacoes and AutorizacaoProtocolo.query.count()==1
        assert verify_audit_chain(1)[0]
        snapshot=json.loads(db.session.get(AutorizacaoProtocolo,rid).resumo)
        assert snapshot['numero']==p.numero and snapshot['requerente']==p.nome
    body=c.get(f'/protocolo/{pid}').get_data(as_text=True)
    assert 'Aguardando autorização de' in body


@pytest.mark.parametrize('decision',['AUTORIZADO','NAO_AUTORIZADO'])
def test_both_decisions_generate_persisted_pdf_and_unlock_without_changing_owner(decision):
    rid=solicit();c=client('autoriza');pid,_=ids()
    with patch('protocol_authorizations.render_authorization_pdf',return_value=b'%PDF-fixture'):
        assert c.post(f'/autorizacoes/{rid}/decidir',data={'decisao':decision}).status_code==302
        assert c.post(f'/autorizacoes/{rid}/decidir',data={'decisao':decision}).status_code==302
        other='NAO_AUTORIZADO' if decision=='AUTORIZADO' else 'AUTORIZADO'
        assert c.post(f'/autorizacoes/{rid}/decidir',data={'decisao':other}).status_code==409
    assert c.get(f'/autorizacoes/{rid}/documento').data==b'%PDF-fixture'
    with app.app_context():
        a=db.session.get(AutorizacaoProtocolo,rid);p=db.session.get(Protocolo,pid)
        assert a.status==decision and a.documento_id and a.decidido_em and a.decidido_por_id==a.autorizador_id
        assert a.decisor_nome=='Pessoa Autorizadora'
        assert (p.responsavel,p.setor_atual_id,p.status)==('admin',1,'RECEBIDO')
        assert p.autorizacao_pendente is None
        assert Anexo.query.filter(Anexo.documento_chave.like('autorizacao-decisao-%')).count()==1
        assert HistoricoProtocolo.query.filter_by(acao='AUTORIZACAO_DECIDIDA').count()==1
        assert verify_audit_chain(1)[0]
    assert client().get(f'/protocolo/{pid}/editar').status_code==200


def test_all_mutations_are_locked_including_json_old_links_and_admin_actions():
    rid=solicit();pid,_=ids();c=client()
    paths=[f'/protocolo/{pid}/editar',f'/protocolo/{pid}/deletar',f'/protocolo/{pid}/anexo/novo',
        f'/protocolo/{pid}/tramitar',f'/protocolo/{pid}/receber',f'/protocolo/{pid}/arquivar',
        f'/protocolo/{pid}/desarquivar',f'/protocolo/{pid}/despachos',f'/protocolo/{pid}/finalizar',
        f'/protocolo/{pid}/solicitar-complemento',f'/protocolo/{pid}/retificar',
        f'/protocolo/{pid}/documento/gerar',f'/protocolo/{pid}/autenticar-emissao',
        f'/protocolo/{pid}/cancelar-emissao']
    for path in paths:
        response=c.post(path,data={}); assert response.status_code==409,(path,response.status_code)
    assert c.get(f'/protocolo/{pid}/editar').status_code==409
    result=c.post('/protocolos/atualizar',json={'protocoloId':str(pid),'novoStatus':'EM ANÁLISE'})
    assert result.status_code==409 and not result.json['sucesso']
    with app.app_context():assert db.session.get(Protocolo,pid).status=='RECEBIDO'


def test_only_assigned_authorizer_can_decide_upload_and_dispatch():
    rid=solicit();pid,_=ids()
    for name in ['admin','outro','tramita']:
        c=client(name)
        assert c.post(f'/autorizacoes/{rid}/decidir',data={'decisao':'AUTORIZADO'}).status_code in (403,404)
        assert c.post(f'/autorizacoes/{rid}/anexo',data={'anexo':(png(),'teste.png')}).status_code in (403,404)
        assert c.get(f'/protocolo/{pid}/despachos/novo').status_code in (302,404,409)
    c=client('autoriza')
    assert c.get('/autorizacoes').status_code==200
    body=c.get(f'/autorizacoes/{rid}').get_data(as_text=True)
    assert 'Pessoa Autorizadora' in body and 'Resumo do pedido' in body
    assert c.post(f'/autorizacoes/{rid}/anexo',data={'anexo':(png(),'analise.png')}).status_code==302
    assert c.get(f'/protocolo/{pid}/despachos/novo').status_code==200
    with patch('protocol_dispatches.render_dispatch_pdf',return_value=b'%PDF-despacho'):
        assert c.post(f'/protocolo/{pid}/despachos',data={'assunto':'Análise','texto':'Manifestação opcional do autorizador.','envio_token':'despacho-token-1234567890123456'}).status_code==302
    with app.app_context():
        a=db.session.get(AutorizacaoProtocolo,rid)
        assert a.status=='PENDENTE' and a.protocolo.autorizacao_pendente
        assert Anexo.query.filter_by(file_name='analise.png').one().enviado_por_id==a.autorizador_id
        assert DespachoProtocolo.query.one().autor_id==a.autorizador_id
        assert verify_audit_chain(1)[0]


def test_read_only_role_with_function_can_dispatch_only_on_assigned_analysis():
    with app.app_context():
        u=Usuario.query.filter_by(login='autoriza').one();u.tipo='consulta';u.pode_autorizar=True;db.session.commit()
    rid=solicit();pid,_=ids();c=client('autoriza')
    assert c.get(f'/protocolo/{pid}/despachos/novo').status_code==200
    assert c.post('/configuracoes').status_code==302
    with patch('protocol_authorizations.render_authorization_pdf',return_value=b'%PDF-fixture'):
        assert c.post(f'/autorizacoes/{rid}/decidir',data={'decisao':'AUTORIZADO'}).status_code==302
    assert c.get(f'/protocolo/{pid}/despachos/novo').status_code==302


def test_failure_to_create_document_keeps_pending_and_can_be_retried():
    rid=solicit();c=client('autoriza');pid,_=ids()
    with patch('protocol_authorizations.render_authorization_pdf',side_effect=RuntimeError('Falha simulada')):
        assert c.post(f'/autorizacoes/{rid}/decidir',data={'decisao':'AUTORIZADO'}).status_code==503
    with app.app_context():
        a=db.session.get(AutorizacaoProtocolo,rid)
        assert a.status=='PENDENTE' and not a.documento_id and not a.decidido_em
        assert not HistoricoProtocolo.query.filter_by(acao='AUTORIZACAO_DECIDIDA').count()
        assert db.session.get(Protocolo,pid).autorizacao_pendente
    with patch('protocol_authorizations.render_authorization_pdf',return_value=b'%PDF-fixture'):
        assert c.post(f'/autorizacoes/{rid}/decidir',data={'decisao':'AUTORIZADO'}).status_code==302


def test_feature_only_global_admin_and_cannot_disable_or_revoke_pending_authorizer():
    rid=solicit();pid,uid=ids();c=client()
    assert c.post('/plataforma/cliente/1/capacidades',data={}).status_code==403
    assert c.post('/admin/usuarios/'+str(uid)+'/status').status_code==409
    assert c.post('/admin/usuarios/'+str(uid)+'/editar',data=dict(nome_completo='Pessoa',email='teste@example.test',tipo='consulta',lotacao_id='0',servidor_id='0')).status_code==409
    global_client=client('global')
    assert global_client.post('/plataforma/cliente/1/capacidades',data={}).status_code==409
    with app.app_context():assert db.session.get(Organizacao,1).autorizacao_protocolos_enabled


def test_feature_disabled_and_cross_tenant_ids_do_not_expose_protocols():
    rid=solicit();pid,_=ids()
    outside=client('fora','cliente-b')
    for path in [f'/autorizacoes/{rid}',f'/autorizacoes/{rid}/documento',f'/protocolo/{pid}']:
        assert outside.get(path).status_code==404
    assert outside.post(f'/autorizacoes/{rid}/decidir',data={'decisao':'AUTORIZADO'}).status_code==404
    with app.app_context():
        foreign=Usuario.query.filter_by(login='fora').one().id
        p=Protocolo.query.filter_by(tenant_id=2).one().id
    assert client(tenant='cliente-b').post(f'/protocolo/{p}/solicitar-autorizacao',data={'autorizador_id':foreign,'envio_token':'feature-desligada-1234567890123'}).status_code==404
    with app.app_context():
        # Um novo processo no mesmo cliente não é exposto por um usuário dedicado.
        q=Protocolo(tenant_id=1,numero='0002/2026',nome='Não atribuído');db.session.add(q);db.session.commit();qid=q.id
    assert client('autoriza').get(f'/protocolo/{qid}').status_code==404


def test_pdf_real_content_has_both_decision_labels_author_and_local_date():
    from protocol_authorizations import render_authorization_pdf
    for status,label in [('AUTORIZADO','AUTORIZO'),('NAO_AUTORIZADO','NÃO AUTORIZO')]:
        with app.test_request_context():
            a=AutorizacaoProtocolo(id=8,tenant_id=1,protocolo=Protocolo.query.filter_by(tenant_id=1).one(),status=status,resumo=json.dumps(dict(numero='1234/2026',requerente='Pessoa Requerente',tipo='LICENÇA')),
                decisor_nome='Pessoa Autorizadora',decisor_login='secretario',decisor_setor='Gabinete',decidido_em=datetime(2026,11,2,18,30,tzinfo=timezone.utc))
            pdf=render_authorization_pdf(a,db.session.get(Organizacao,1))
            text=' '.join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
            text = ' '.join(text.split())
            assert label in text and '1234/2026' in text and 'Pessoa Autorizadora' in text
            assert 'o prosseguimento do Protocolo' in text
            assert 'atendimento do pedido' not in text
            assert '02/11/2026 às 15:30:00' in text


def test_decision_attachment_cannot_be_replaced_and_is_not_part_of_original_request():
    rid=solicit();c=client('autoriza');pid,_=ids()
    with patch('protocol_authorizations.render_authorization_pdf',return_value=b'%PDF-fixture'):
        c.post(f'/autorizacoes/{rid}/decidir',data={'decisao':'NAO_AUTORIZADO'})
    with app.app_context():
        a=db.session.get(AutorizacaoProtocolo,rid);aid=a.documento_id
        from protocol_export import request_attachments
        assert a.documento not in request_attachments(a.protocolo.anexos)
    owner=client()
    assert owner.post(f'/protocolo/{pid}/anexo/novo',data={'documento_id':str(aid),'anexo':(png(),'alterar.png')}).status_code==409
    assert owner.post(f'/anexo/{aid}/deletar').status_code==409


def test_csrf_is_required_for_request_decision_and_upload():
    rid=solicit();pid,_=ids();owner=client();authorizer=client('autoriza')
    app.config['WTF_CSRF_ENABLED']=True
    try:
        assert owner.post(f'/protocolo/{pid}/solicitar-autorizacao',data={}).status_code==400
        assert authorizer.post(f'/autorizacoes/{rid}/decidir',data={'decisao':'AUTORIZADO'}).status_code==400
        assert authorizer.post(f'/autorizacoes/{rid}/anexo',data={}).status_code==400
    finally:app.config['WTF_CSRF_ENABLED']=False


def test_feature_activation_is_per_client_and_audited_by_platform_admin_only():
    from models import OrganizacaoCapacidadeEvento
    with app.app_context():
        db.session.get(Organizacao,1).autorizacao_protocolos_enabled=False; db.session.commit()
    g=client('global')
    assert g.post('/plataforma/cliente/1/capacidades',data={'autorizacao_protocolos_enabled':'on'}).status_code==302
    with app.app_context():
        assert db.session.get(Organizacao,1).autorizacao_protocolos_enabled
        assert not db.session.get(Organizacao,2).autorizacao_protocolos_enabled
        assert OrganizacaoCapacidadeEvento.query.filter_by(organizacao_id=1).one().autorizacao_protocolos_enabled
    page=client().get('/configuracoes').get_data(as_text=True)
    assert 'Autorizador' in page and 'Autorização de protocolos' not in page
    assert g.post('/plataforma/cliente/1/capacidades',data={}).status_code==302
    with app.app_context(): assert not db.session.get(Organizacao,1).autorizacao_protocolos_enabled


def test_new_authorizer_creation_and_role_grant_are_tenant_scoped():
    c=client()
    data=dict(nome_completo='Autoriza Novo',login='novosecretario',email='novo@example.test',senha='Senha-Segura-2026',tipo='autorizador',lotacao_id='0',servidor_id='0',submit='Criar Usuário')
    assert c.post('/admin/usuarios/novo',data=data).status_code==302
    with app.app_context():
        u=Usuario.query.filter_by(login='novosecretario').one()
        assert u.tenant_id==1 and u.pode_autorizar and u.tipo=='autorizador'
    other=client(tenant='cliente-b')
    data['login']='outrosecretario'
    assert other.post('/admin/usuarios/novo',data=data).status_code==400
    with app.app_context(): assert not Usuario.query.filter_by(login='outrosecretario').first()


def test_recipient_validation_and_inactive_authorizer_do_not_lock_protocol():
    c=client();pid,uid=ids()
    with app.app_context():
        Usuario.query.filter_by(login='autoriza').one().status='inativo'
        foreign=Usuario.query.filter_by(login='fora').one().id
        db.session.commit()
    for recipient in [str(uid),str(foreign),'1 OR 1=1','9'*6000,'',str(2147483648)]:
        r=c.post(f'/protocolo/{pid}/solicitar-autorizacao',data={'autorizador_id':recipient,'envio_token':'validacao-destino-12345678901234'})
        assert r.status_code==400
    with app.app_context(): assert not db.session.get(Protocolo,pid).autorizacao_pendente


def test_request_is_in_existing_actions_menu_and_form_is_only_in_modal():
    pid,_=ids();body=client().get(f'/protocolo/{pid}').get_data(as_text=True)
    assert 'Autorização do protocolo</h2>' not in body
    assert 'data-bs-target="#modalSolicitarAutorizacao"' in body
    assert 'class="modal fade" id="modalSolicitarAutorizacao"' in body
    menu=body.split('>Outras ações</button>',1)[1].split('</ul>',1)[0]
    assert 'Solicitar autorização' in menu
    modal=body.split('id="modalSolicitarAutorizacao"',1)[1].split('</form>',1)[0]
    assert 'name="autorizador_id"' in modal
    assert 'textarea' not in modal
