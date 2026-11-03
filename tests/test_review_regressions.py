"""Casos encontrados na revisão visual e de entradas inválidas."""
from unittest.mock import patch
import pytest
import test_authorizations as fixture
from app import app, db, bcrypt, _strong_password, _portal_password_valid
from models import Usuario, Anexo

setup_function=fixture.setup_function
teardown_function=fixture.teardown_function


@pytest.mark.parametrize('value',['A1'+'x'*80, 'Á1'+'é'*36])
def test_long_passwords_are_rejected_without_failing_login_or_password_change(value):
    assert not _strong_password(value) and not _portal_password_valid(value)
    client=fixture.client()
    for data in [dict(senha_atual='senha-segura',senha_nova=value,confirmar_senha=value),
                 dict(senha_atual=value,senha_nova='NovaSenha2026',confirmar_senha='NovaSenha2026')]:
        assert client.post('/minha-conta/trocar-senha',data=data).status_code==200
    with app.app_context():
        user=Usuario.query.filter_by(tenant_id=1,login='admin').one()
        assert bcrypt.check_password_hash(user.senha,'senha-segura')
    for path in ['/entrar/cliente-a','/login']:
        visitor=app.test_client()
        assert visitor.post(path,data={'login':'admin','senha':value}).status_code in (200,302)


def test_password_byte_boundary_preserves_valid_accented_passwords():
    assert _strong_password('á'*36)
    assert not _strong_password('á'*37)
    assert _portal_password_valid('Aa1'+'é'*34)
    assert not _portal_password_valid('Aa1'+'é'*35)


def test_decision_document_has_download_without_offering_replacement():
    rid=fixture.solicit();pid,_=fixture.ids()
    with patch('protocol_authorizations.render_authorization_pdf',return_value=b'%PDF-test'):
        fixture.client('autoriza').post(f'/autorizacoes/{rid}/decidir',data={'decisao':'AUTORIZADO'})
    with app.app_context():
        decision=Anexo.query.filter(Anexo.documento_chave.like('autorizacao-decisao-%')).one();docid=decision.id
    html=fixture.client().get(f'/protocolo/{pid}').get_data(as_text=True)
    assert f'/anexo/{docid}/download' in html
    assert f'substituir-arquivo-{docid}' not in html
