from pathlib import Path
from datetime import date
from unittest.mock import patch
import io
import test_multitenancy as base
from app import app, db, parse_functional_date, _email_code_hash
from models import Servidor, Usuario, Organizacao, LoginTentativa, Protocolo, TipoRequerimento
from openpyxl import Workbook

def setup_module():
    Path(base._test_directory.name).mkdir(exist_ok=True)
    base.setup_module()
    with app.app_context():
        db.session.get(Organizacao, 1).portal_servidor_remoto_enabled = True
        server = Servidor(tenant_id=1, matricula='PROFILE', nome='Pessoa Perfil', cpf='01234567890', nome_mae='Maria', nascimento=date(1990,1,1))
        db.session.add(server)
        db.session.flush()
        db.session.add(Usuario(tenant_id=1, nome='Pessoa', nome_completo=server.nome, login='PROFILE',
            senha=base.bcrypt.generate_password_hash('SenhaTeste123').decode(), tipo='requerente',
            servidor_id=server.id, email='old@example.test', status='ativo'))
        db.session.commit()

def teardown_module():
    base.teardown_module()

def portal_client():
    client = app.test_client()
    assert client.post('/portal/cliente-a/entrar', data={'login':'PROFILE','senha':'SenhaTeste123'}).status_code == 302
    return client

def test_logged_portal_user_can_open_public_tracking_without_internal_access():
    with app.app_context():
        protocol=Protocolo.query.filter_by(nome='Dado exclusivo A').one()
        token=protocol.consulta_token
    client=portal_client()
    assert client.get(f'/consulta/{token}').status_code == 200
    invalid=client.post(f'/consulta/{token}',data={'matricula':'incorreta'}).get_data(as_text=True)
    assert '0001/2026' not in invalid
    valid=client.post(f'/consulta/{token}',data={'matricula':'MAT-A'}).get_data(as_text=True)
    assert '0001/2026' in valid
    assert client.get('/configuracoes').status_code == 302

def test_invalid_numeric_date_rejected_before_database():
    for value in (1011990, None, 45000, '31/02/1990'):
        try:
            parse_functional_date(value)
            assert False
        except ValueError:
            pass
    assert parse_functional_date('01/01/1990') == date(1990,1,1)
    book = Workbook()
    book.active.append(['matricula','nome','cpf','data_nascimento','nome_mae'])
    book.active.append(['BADDATE','Pessoa','01234567890',1011990,'Maria'])
    stream=io.BytesIO(); book.save(stream); stream.seek(0)
    client=app.test_client(); base.login(client,'cliente-a')
    result=client.post('/admin/servidores/importar',data={'arquivo':(stream,'cadastro.xlsx')},follow_redirects=True)
    assert result.status_code == 200 and 'Data de nascimento inválida na linha 2' in result.get_data(as_text=True)
    with app.app_context():
        assert not Servidor.query.filter_by(matricula='BADDATE').first()

def test_profile_contact_and_internal_accounts_are_separate():
    client=portal_client()
    assert 'Meus dados' in client.get('/portal').get_data(as_text=True)
    assert client.post('/portal/meus-dados',data={'email':'old@example.test','telefone':'88999999999','endereco':'Rua Teste'}).status_code == 302
    with app.app_context():
        user=Usuario.query.filter_by(login='PROFILE').one()
        assert user.endereco == 'Rua Teste' and user.telefone == '88999999999'
    admin=app.test_client(); base.login(admin,'cliente-a')
    assert 'PROFILE' not in admin.get('/configuracoes').get_data(as_text=True)
    with app.app_context():
        server_id=Servidor.query.filter_by(matricula='PROFILE').one().id
    assert admin.get(f'/admin/servidores/{server_id}/editar').status_code == 200
    other=app.test_client(); base.login(other,'cliente-b')
    assert other.get(f'/admin/servidores/{server_id}/editar').status_code == 404

def test_email_change_requires_code_and_cooldown_survives_sessions():
    client=portal_client()
    with patch('app._send_account_email') as send:
        client.post('/portal/meus-dados',data={'email':'new@example.test','telefone':'88','endereco':'Rua'})
        assert send.call_count == 1
        second=portal_client()
        second.post('/portal/meus-dados',data={'email':'other@example.test'})
        assert send.call_count == 1
    with app.app_context():
        user=Usuario.query.filter_by(login='PROFILE').one(); user_id=user.id
        assert user.email == 'old@example.test'
    with client.session_transaction() as state:
        pending=dict(state['portal_email_change']); pending['hash']=_email_code_hash(user_id,'123456'); state['portal_email_change']=pending
    client.post('/portal/meus-dados',data={'acao':'confirmar_email','codigo':'000000'})
    with app.app_context():
        assert Usuario.query.filter_by(login='PROFILE').one().email == 'old@example.test'
    client.post('/portal/meus-dados',data={'acao':'confirmar_email','codigo':'123456'})
    with app.app_context():
        assert Usuario.query.filter_by(login='PROFILE').one().email == 'new@example.test'

def test_receipt_with_pin_preserves_submission_and_both_signature_blocks():
    with app.app_context():
        db.session.get(Organizacao,1).emissao_eletronica_protocolista_enabled=True
        Usuario.query.filter_by(login='admin',tenant_id=1).one().pin_hash=base.bcrypt.generate_password_hash('123456').decode()
        db.session.add(TipoRequerimento(tenant_id=1,nome='Teste recebimento',ativo=True))
        db.session.commit()
    portal=portal_client()
    with patch('app.render_protocol_pdf',return_value=b'%PDF-1.7 original'):
        assert portal.post('/portal/novo',data={'tipo_requerimento':'Teste recebimento','requer_ao':'Secretaria de teste do portal','observacoes':'Pedido teste','declaracao':'on'}).status_code==302
    with app.app_context():
        protocol=Protocolo.query.filter_by(tipo_requerimento='Teste recebimento').one(); protocol_id=protocol.id
        original_hash=protocol.emissao_eletronica.pdf_sha256
    admin=app.test_client(); base.login(admin,'cliente-a')
    pending = admin.get('/pendencias-recebimento').get_data(as_text=True)
    assert f'/protocolo/{protocol_id}' in pending and 'Aguardando recebimento inicial' in pending
    other = app.test_client(); base.login(other, 'cliente-b')
    assert f'/protocolo/{protocol_id}' not in other.get('/pendencias-recebimento').get_data(as_text=True)
    admin.post(f'/protocolo/{protocol_id}/receber-portal',data={'pin':'000000'})
    with app.app_context():
        assert db.session.get(Protocolo,protocol_id).aguardando_recebimento_inicial
    rendered=[]
    def pdf(protocol,emission):
        from flask import render_template
        rendered.append(render_template('pdf_template.html',protocolo=protocol,emissao=emission,
            organizacao=db.session.get(Organizacao,1),pdf_logo_url='',qr_code_url='',qr_validacao_url=''))
        return b'%PDF-1.7 recebido'
    with patch('app.render_protocol_pdf',side_effect=pdf):
        response = admin.post(f'/protocolo/{protocol_id}/receber-portal',data={'pin':'123456'})
        assert response.status_code == 302
        assert response.headers['Location'] == f'/protocolo/{protocol_id}'
    assert 'REQUERIMENTO ENVIADO ELETRONICAMENTE' in rendered[0]
    assert 'PROTOCOLO EMITIDO ELETRONICAMENTE' in rendered[0]
    assert 'PROTOCOLO DE REQUERIMENTO' in rendered[0]
    assert 'REQUERIMENTO RECEBIDO' not in rendered[0] and 'VERSÃO' not in rendered[0]
    with app.app_context():
        protocol=db.session.get(Protocolo,protocol_id)
        assert protocol.status=='RECEBIDO' and protocol.responsavel=='admin'
        assert len(protocol.emissoes_eletronicas)==2 and protocol.envio_requerente.pdf_sha256==original_hash
        assert protocol.envio_requerente.status == 'SUBSTITUIDA'
        assert not any(h.acao == 'RETIFICACAO_AUTENTICADA' for h in protocol.historico)
    assert admin.post(f'/protocolo/{protocol_id}/receber-portal',data={'pin':'123456'}).status_code==409
    assert '<option value="Secretaria de teste do portal" selected>' in admin.get(f'/protocolo/{protocol_id}/retificar').get_data(as_text=True)
    assert f'/protocolo/{protocol_id}' not in admin.get('/pendencias-recebimento').get_data(as_text=True)
