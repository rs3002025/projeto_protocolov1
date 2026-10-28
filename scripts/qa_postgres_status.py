"""Regressão em PostgreSQL descartável local da CI; nunca aceita banco remoto."""
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

url = os.environ['QA_DATABASE_URL']
parsed = urlsplit(url)
if parsed.hostname not in ('localhost', '127.0.0.1') or parsed.path != '/muniprot_qa':
    raise RuntimeError('Use somente o PostgreSQL descartável local muniprot_qa.')
os.environ.update(DATABASE_URL=url, SECRET_KEY='disposable-ci-only-key', TENANT_SUBDOMAINS_ENABLED='false')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app, db
from models import Organizacao, Usuario, Protocolo, HistoricoProtocolo

app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
with app.app_context():
    assert db.engine.dialect.name == 'postgresql'
    db.create_all()
    a = Organizacao(nome='QA A', slug='prefeitura')
    b = Organizacao(nome='QA B', slug='qa-b')
    db.session.add_all([a, b]); db.session.flush()
    user = Usuario(tenant_id=a.id, nome='QA Admin', login='qa_admin', tipo='admin', senha='fixture-only')
    p = Protocolo(tenant_id=a.id, numero='0001/2026', nome='QA', status='RECEBIDO')
    foreign = Protocolo(tenant_id=b.id, numero='0001/2026', nome='QA B', status='RECEBIDO')
    db.session.add_all([user, p, foreign]); db.session.commit()
    uid, pid, foreign_id = user.get_id(), p.id, foreign.id
try:
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'], session['_fresh'] = uid, True
    def update(identifier, status='EM ANÁLISE'):
        return client.post('/protocolos/atualizar', json={'protocoloId': identifier, 'novoStatus': status, 'observacao': 'Validação em PostgreSQL.'})
    assert update(str(pid)).status_code == 200  # Mesmo tipo enviado pelo input HTML.
    assert update(pid, 'PENDENTE DE DOCUMENTO').status_code == 200
    assert update(str(pid), 'PENDENTE DE DOCUMENTO').status_code == 200
    for value in (None, True, 0, -1, 1.5, {}, [], '1 OR 1=1', '9'*100):
        assert update(value).status_code == 400, value
    assert update(str(foreign_id)).status_code == 404
    assert update('2147483647').status_code == 404
    with app.app_context():
        assert db.session.get(Protocolo, pid).status == 'PENDENTE DE DOCUMENTO'
        assert HistoricoProtocolo.query.filter_by(protocolo_id=pid).count() == 2
        assert db.session.get(Protocolo, foreign_id).status == 'RECEBIDO'
    app.config['WTF_CSRF_ENABLED'] = True
    assert update(str(pid)).status_code == 400
    app.config['WTF_CSRF_ENABLED'] = False
    with client.session_transaction() as session:
        session.clear()
    assert update(str(pid)).status_code == 401
    print('PostgreSQL: atualização textual/numérica, idempotência, dados inválidos, isolamento, CSRF e sessão aprovados.')
finally:
    with app.app_context():
        db.session.remove(); db.drop_all(); db.engine.dispose()
