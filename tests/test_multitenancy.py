import os
import tempfile
import io
import base64
from datetime import date

os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('DATABASE_URL', 'sqlite:///' + tempfile.mktemp(suffix='.sqlite3'))

from app import app, bcrypt, db
from models import Lotacao, Movimentacao, Organizacao, Protocolo, Usuario


def setup_module():
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.app_context():
        db.drop_all()
        db.create_all()
        a = Organizacao(nome='Cliente A', slug='cliente-a')
        b = Organizacao(nome='Cliente B', slug='cliente-b')
        db.session.add_all([a, b])
        db.session.flush()
        password = bcrypt.generate_password_hash('senha-segura').decode('utf-8')
        db.session.add_all([
            Usuario(tenant_id=a.id, nome='Ana', nome_completo='Ana A', login='admin', senha=password, tipo='admin'),
            Usuario(tenant_id=b.id, nome='Bia', nome_completo='Bia B', login='admin', senha=password, tipo='admin'),
            Usuario(tenant_id=a.id, nome='Cris', nome_completo='Cris Consulta', login='consulta', senha=password, tipo='consulta'),
        ])
        db.session.add_all([
            Lotacao(tenant_id=a.id, nome='Protocolo'),
            Lotacao(tenant_id=a.id, nome='Jurídico'),
        ])
        db.session.flush()
        db.session.add_all([
            Protocolo(tenant_id=a.id, numero='0001/2026', nome='Dado exclusivo A', matricula='MAT-A', data_solicitacao=date.today()),
            Protocolo(tenant_id=b.id, numero='0001/2026', nome='Dado exclusivo B', matricula='MAT-B', data_solicitacao=date.today()),
        ])
        db.session.commit()


def login(client, organizacao):
    return client.post('/login', data={
        'organizacao': organizacao,
        'login': 'admin',
        'senha': 'senha-segura',
    }, follow_redirects=True)


def test_listagem_nao_vaza_dados_entre_clientes():
    client = app.test_client()
    login(client, 'cliente-a')
    response = client.get('/protocolos')
    assert response.status_code == 200
    assert b'Dado exclusivo A' in response.data
    assert b'Dado exclusivo B' not in response.data


def test_acesso_direto_a_protocolo_de_outro_cliente_retorna_404():
    with app.app_context():
        protocolo_b = Protocolo.query.filter_by(nome='Dado exclusivo B').one()
        protocolo_b_id = protocolo_b.id
    client = app.test_client()
    login(client, 'cliente-a')
    assert client.get(f'/protocolo/{protocolo_b_id}').status_code == 404


def test_mesmo_login_e_numero_podem_existir_em_clientes_distintos():
    with app.app_context():
        assert Usuario.query.filter_by(login='admin').count() == 2
        assert Protocolo.query.filter_by(numero='0001/2026').count() == 2


def test_consulta_publica_usa_organizacao_e_nao_expoe_requerente():
    with app.app_context():
        token = Protocolo.query.filter_by(nome='Dado exclusivo A').one().consulta_token
    client = app.test_client()
    response = client.get(f'/consulta/{token}')
    assert response.status_code == 200
    assert b'0001/2026' not in response.data
    assert b'Dado exclusivo A' not in response.data
    response = client.post(f'/consulta/{token}', data={'matricula': 'incorreta'})
    assert b'0001/2026' not in response.data
    response = client.post(f'/consulta/{token}', data={'matricula': 'MAT-A'})
    assert b'0001/2026' in response.data
    assert b'Dado exclusivo A' not in response.data
    assert client.get('/consulta/token-inexistente').status_code == 404
    assert client.get('/consulta/cliente-a/2026/0001').status_code == 404


def test_consulta_publica_bloqueia_forca_bruta():
    with app.app_context():
        token = Protocolo.query.filter_by(nome='Dado exclusivo B').one().consulta_token
    client = app.test_client()
    for _ in range(5):
        assert client.post(f'/consulta/{token}', data={'matricula': 'incorreta'}).status_code == 200
    assert client.post(f'/consulta/{token}', data={'matricula': 'incorreta'}).status_code == 429


def test_logo_personalizada_fica_isolada_por_organizacao():
    png = base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
    )
    client = app.test_client()
    login(client, 'cliente-a')
    response = client.post('/admin/identidade/logo', data={
        'logo': (io.BytesIO(png), 'logo.png'),
        'salvar': 'Salvar logo',
    }, content_type='multipart/form-data', follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert Organizacao.query.filter_by(slug='cliente-a').one().logo_data
        assert Organizacao.query.filter_by(slug='cliente-b').one().logo_data is None
    response = client.get('/identidade/cliente-a/logo')
    assert response.status_code == 200
    assert response.content_type.startswith('image/png')


def test_tramitacao_registra_destino_e_historico():
    with app.app_context():
        protocolo = Protocolo.query.filter_by(nome='Dado exclusivo A').one()
        destino = Lotacao.query.filter_by(nome='Jurídico').one()
        protocolo_id, destino_id = protocolo.id, destino.id
    client = app.test_client()
    login(client, 'cliente-a')
    response = client.post(f'/protocolo/{protocolo_id}/tramitar', data={
        'setor_destino_id': destino_id,
        'observacao': 'Análise jurídica necessária',
    })
    assert response.status_code == 302
    with app.app_context():
        movimento = Movimentacao.query.filter_by(protocolo_id=protocolo_id).one()
        assert movimento.setor_destino_id == destino_id
        assert movimento.recebido_em is None
        assert movimento.protocolo.status == 'EM TRAMITAÇÃO'


def test_perfil_consulta_nao_pode_excluir():
    with app.app_context():
        protocolo = Protocolo.query.filter_by(nome='Dado exclusivo A').one()
        protocolo_id = protocolo.id
    client = app.test_client()
    client.post('/login', data={
        'organizacao': 'cliente-a', 'login': 'consulta', 'senha': 'senha-segura'
    })
    assert client.post(f'/protocolo/{protocolo_id}/deletar').status_code == 302
    with app.app_context():
        assert db.session.get(Protocolo, protocolo_id) is not None
