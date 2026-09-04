import os
import tempfile
import io
from pathlib import Path
from datetime import date, datetime, timedelta

# Nunca herdar DATABASE_URL do Railway: esta suíte recria todas as tabelas.
_test_directory = tempfile.TemporaryDirectory(prefix='protocolo-tests-')
os.environ['SECRET_KEY'] = 'test-secret-key'
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(_test_directory.name) / 'tests.sqlite3')

from app import app, bcrypt, db
from models import Lotacao, Movimentacao, Organizacao, Protocolo, Usuario, ConsultaPublicaTentativa


def teardown_module():
    with app.app_context():
        db.session.remove()
        db.engine.dispose()
    _test_directory.cleanup()


def setup_module():
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.app_context():
        assert db.engine.url.drivername == 'sqlite'
        assert Path(db.engine.url.database).resolve().parent == Path(_test_directory.name).resolve()
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


def test_consulta_publica_reutiliza_janela_expirada_e_aceita_unicode():
    client = app.test_client()
    with app.app_context():
        protocolo = Protocolo.query.filter_by(nome='Dado exclusivo A').one()
        token, protocolo_id = protocolo.consulta_token, protocolo.id
    assert client.post(f'/consulta/{token}', data={'matricula': 'inválida'}).status_code == 200
    with app.app_context():
        tentativa = ConsultaPublicaTentativa.query.filter_by(protocolo_id=protocolo_id).one()
        tentativa.janela_iniciada_em = datetime.utcnow() - timedelta(minutes=16)
        db.session.commit()
    assert client.post(f'/consulta/{token}', data={'matricula': 'outra'}).status_code == 200
    with app.app_context():
        tentativa = ConsultaPublicaTentativa.query.filter_by(protocolo_id=protocolo_id).one()
        assert tentativa.tentativas == 1
    assert b'0001/2026' in client.post(f'/consulta/{token}', data={'matricula': 'MAT-A'}).data


def test_relatorios_e_exportacao_exigem_permissao():
    client = app.test_client()
    client.post('/login', data={'organizacao': 'cliente-a', 'login': 'consulta', 'senha': 'senha-segura'})
    for path in ['/relatorios', '/protocolos/backup/excel']:
        assert client.get(path, headers={'Content-Type': 'application/json'}).status_code == 403
    html = client.get('/protocolos').get_data(as_text=True)
    assert 'Exportar para Excel' not in html
    assert '>Relatórios</a>' not in html
    login(client, 'cliente-a')  # A sessão de consulta não deve ser elevada pelo formulário.
    assert client.get('/relatorios', headers={'Content-Type': 'application/json'}).status_code == 403


def test_csrf_rejeita_operacao_sem_token_e_aceita_formulario_legitimo():
    import re
    client = app.test_client()
    app.config['WTF_CSRF_ENABLED'] = True
    try:
        assert client.post('/login', data={}).status_code == 400
        html = client.get('/login').get_data(as_text=True)
        token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html).group(1)
        response = client.post('/login', data={
            'organizacao': 'cliente-a', 'login': 'admin', 'senha': 'senha-segura',
            'csrf_token': token,
        })
        assert response.status_code == 302
        assert client.post('/protocolos/atualizar', json={}).status_code == 400
        response = client.post('/protocolos/atualizar', json={}, headers={'X-CSRFToken': token})
        assert b'CSRF' not in response.data
        with app.app_context():
            protocolo_id = Protocolo.query.filter_by(nome='Dado exclusivo A').one().id
        for path in ['/protocolo/novo', '/configuracoes', f'/protocolo/{protocolo_id}']:
            response = client.get(path)
            assert response.status_code == 200
            for form in re.findall(r'<form\b[\s\S]*?</form>', response.get_data(as_text=True)):
                if re.search(r'method="POST"', form, re.I):
                    assert 'name="csrf_token"' in form
    finally:
        app.config['WTF_CSRF_ENABLED'] = False


def test_logo_personalizada_fica_isolada_por_organizacao():
    client = app.test_client()
    login(client, 'cliente-a')
    primeira = Path('static/img/logo.png').read_bytes()
    segunda = Path('static/img/logobrasao.png').read_bytes()
    response = client.post('/admin/identidade/logo', data={
        'logo': (io.BytesIO(primeira), 'logo.png'),
        'salvar': 'Salvar logo',
    }, content_type='multipart/form-data', follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        primeira_gravada = Organizacao.query.filter_by(slug='cliente-a').one().logo_data
        assert primeira_gravada
        assert Organizacao.query.filter_by(slug='cliente-b').one().logo_data is None
    response = client.post('/admin/identidade/logo', data={
        'logo': (io.BytesIO(segunda), 'brasao.png'),
        'salvar': 'Salvar logo',
    }, content_type='multipart/form-data', follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        segunda_gravada = Organizacao.query.filter_by(slug='cliente-a').one().logo_data
        assert segunda_gravada and segunda_gravada != primeira_gravada
    response = client.get('/identidade/cliente-a/logo')
    assert response.status_code == 200
    assert response.content_type.startswith('image/png')
    response = client.post('/admin/identidade/logo', data={
        'remover': 'Restaurar logo padrão',
    }, content_type='multipart/form-data', follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert Organizacao.query.filter_by(slug='cliente-a').one().logo_data is None
    response = client.get('/identidade/cliente-a/logo')
    assert response.status_code == 302
    assert 'logo-sysprot.svg' in response.headers['Location']


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
