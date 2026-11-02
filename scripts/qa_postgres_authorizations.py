"""Concorrência e integridade em PostgreSQL local descartável; nunca em produção."""
import io
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import patch
from urllib.parse import urlsplit

url = os.environ['QA_DATABASE_URL']
parsed = urlsplit(url)
if parsed.hostname not in ('localhost', '127.0.0.1') or parsed.path != '/muniprot_qa' or parsed.username != 'qa':
    raise RuntimeError('Use apenas o PostgreSQL local descartável muniprot_qa, usuário qa.')
os.environ.update(DATABASE_URL=url, SECRET_KEY='disposable-auth-qa-only', TENANT_SUBDOMAINS_ENABLED='false')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app, db, bcrypt, verify_audit_chain
from models import Organizacao, Usuario, Protocolo, AutorizacaoProtocolo, Anexo
from sqlalchemy import text

app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
password='Senha-Ficticia-QA-2026'
with app.app_context():
    assert db.engine.dialect.name == 'postgresql'
    db.create_all()
    org=Organizacao(nome='QA autorizações',slug='qa-auth',autorizacao_protocolos_enabled=True)
    db.session.add(org);db.session.flush()
    pwd=bcrypt.generate_password_hash(password).decode()
    owner=Usuario(tenant_id=org.id,nome='Responsável QA',login='owner',tipo='admin',senha=pwd)
    approver=Usuario(tenant_id=org.id,nome='Autorizador QA',login='approver',tipo='autorizador',senha=pwd)
    protocol=Protocolo(tenant_id=org.id,numero='0001/2026',nome='Pessoa Fictícia',status='RECEBIDO',responsavel='owner')
    db.session.add_all([owner,approver,protocol]);db.session.commit()
    tenant,pid,uid=org.id,protocol.id,approver.id


def client(name):
    c=app.test_client()
    assert c.post('/entrar/qa-auth',data={'login':name,'senha':password}).status_code==302
    return c


try:
    first,second=client('owner'),client('owner')
    barrier=Barrier(2)
    def request_one(pair):
        c,token=pair;barrier.wait(timeout=10)
        return c.post(f'/protocolo/{pid}/solicitar-autorizacao',data={'autorizador_id':uid,'envio_token':token}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses=list(pool.map(request_one,[(first,'token-primeiro-12345678901234'),(second,'token-segundo-123456789012345')]))
    assert sorted(statuses)==[302,409],statuses
    with app.app_context():
        a=AutorizacaoProtocolo.query.filter_by(tenant_id=tenant).one();rid=a.id
        assert a.status=='PENDENTE' and a.protocolo.responsavel=='owner'
        assert verify_audit_chain(tenant)[0]
        indexes=db.session.execute(text("SELECT indexdef FROM pg_indexes WHERE indexname='uq_autorizacao_pendente'" )).scalar()
        assert 'UNIQUE' in indexes and 'WHERE' in indexes
    a,b=client('approver'),client('approver')
    with patch('protocol_authorizations.render_authorization_pdf',side_effect=RuntimeError('Falha de PDF simulada em QA')):
        assert a.post(f'/autorizacoes/{rid}/decidir',data={'decisao':'AUTORIZADO'}).status_code==503
    with app.app_context():
        row=db.session.get(AutorizacaoProtocolo,rid)
        assert row.status=='PENDENTE' and row.documento_id is None
    barrier=Barrier(2)
    def decide(c):
        barrier.wait(timeout=10)
        return c.post(f'/autorizacoes/{rid}/decidir',data={'decisao':'AUTORIZADO'}).status_code
    with patch('protocol_authorizations.render_authorization_pdf',return_value=b'%PDF-fixture-concurrency'):
        with ThreadPoolExecutor(max_workers=2) as pool: statuses=list(pool.map(decide,[a,b]))
    assert statuses==[302,302],statuses
    with app.app_context():
        row=db.session.get(AutorizacaoProtocolo,rid)
        assert row.status=='AUTORIZADO' and row.decidido_por_id==uid and row.documento_id
        assert Anexo.query.filter_by(tenant_id=tenant,documento_chave=f'autorizacao-decisao-{rid}').count()==1
        assert row.protocolo.responsavel=='owner' and row.protocolo.autorizacao_pendente is None
        assert verify_audit_chain(tenant)[0]
    assert a.get(f'/autorizacoes/{rid}/documento').data==b'%PDF-fixture-concurrency'
    print('PostgreSQL: solicitações concorrentes, decisão idempotente concorrente, rollback de PDF e auditoria aprovados.')
finally:
    with app.app_context():
        db.session.remove();db.drop_all();db.engine.dispose()
