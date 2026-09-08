import os
import tempfile
import io
import sys
import types
from unittest.mock import patch
from openpyxl import load_workbook
from flask import render_template
from pathlib import Path
from datetime import date, datetime, timedelta

# Nunca herdar DATABASE_URL do Railway: esta suíte recria todas as tabelas.
_test_directory = tempfile.TemporaryDirectory(prefix='protocolo-tests-')
os.environ['SECRET_KEY'] = 'test-secret-key'
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(_test_directory.name) / 'tests.sqlite3')

from app import app, bcrypt, db
from models import Lotacao, Movimentacao, Organizacao, Protocolo, Usuario, ConsultaPublicaTentativa, LoginTentativa, Anexo, HistoricoProtocolo


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


def test_login_nao_redireciona_para_site_externo():
    client = app.test_client()
    response = client.post('/login?next=https://evil.example/coleta', data={
        'organizacao': 'cliente-a', 'login': 'admin', 'senha': 'senha-segura',
    })
    assert response.status_code == 302
    assert response.headers['Location'] == '/home'

    client.post('/logout')
    response = client.post('/login?next=/protocolos', data={
        'organizacao': 'cliente-a', 'login': 'admin', 'senha': 'senha-segura',
    })
    assert response.headers['Location'] == '/protocolos'


def test_login_bloqueia_forca_bruta_sem_revelar_usuario():
    client = app.test_client()
    dados = {'organizacao': 'cliente-a', 'login': 'inexistente', 'senha': 'incorreta'}
    for _ in range(5):
        response = client.post('/login', data=dados)
        assert response.status_code == 200
        assert 'Não foi possível autenticar' in response.get_data(as_text=True)
    bloqueado = client.post('/login', data=dados)
    assert bloqueado.status_code == 429
    assert 'Aguarde alguns minutos' in bloqueado.get_data(as_text=True)
    with app.app_context():
        tentativa = LoginTentativa.query.one()
        tentativa.janela_iniciada_em = datetime.utcnow() - timedelta(minutes=16)
        tentativa.bloqueado_ate = None
        db.session.commit()
    assert client.post('/login', data=dados).status_code == 200


def test_health_verifica_a_conexao_com_o_banco():
    client = app.test_client()
    response = client.get('/health')
    assert response.status_code == 200
    assert response.get_json() == {'status': 'ok', 'database': 'ok'}
    with patch.object(db.session, 'execute', side_effect=RuntimeError('banco indisponivel')):
        response = client.get('/health')
    assert response.status_code == 503
    assert response.get_json() == {'status': 'indisponivel', 'database': 'erro'}


def test_cabecalhos_protegem_dados_e_transporte():
    client = app.test_client()
    login(client, 'cliente-a')
    response = client.get('/protocolos', base_url='https://localhost')
    assert response.headers['Cache-Control'] == 'no-store, max-age=0'
    assert response.headers['Pragma'] == 'no-cache'
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert response.headers['X-Frame-Options'] == 'DENY'
    assert response.headers['Strict-Transport-Security'].startswith('max-age=31536000')
    assert "object-src 'none'" in response.headers['Content-Security-Policy']
    assert response.headers['Permissions-Policy'] == 'camera=(), microphone=(), geolocation=()'
    assert app.config['MAX_CONTENT_LENGTH'] == 21 * 1024 * 1024


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
    for path in ['/api/usuarios', '/api/servidor/MAT-A', '/api/servidores/search?nome=Ana',
                 '/protocolos/ultimoNumero/2026']:
        assert client.get(path, headers={'Content-Type': 'application/json'}).status_code == 403
    html = client.get('/protocolos').get_data(as_text=True)
    assert 'Exportar para Excel' not in html
    assert '>Relatórios</a>' not in html
    login(client, 'cliente-a')  # A sessão de consulta não deve ser elevada pelo formulário.
    assert client.get('/relatorios', headers={'Content-Type': 'application/json'}).status_code == 403


def test_logout_exige_post_e_csrf_quando_habilitado():
    client = app.test_client()
    login(client, 'cliente-a')
    assert client.get('/logout').status_code == 405
    app.config['WTF_CSRF_ENABLED'] = True
    try:
        assert client.post('/logout').status_code == 400
        html = client.get('/home').get_data(as_text=True)
        import re
        token = re.search(r'action="/logout"[\s\S]*?name="csrf_token" value="([^"]+)"', html).group(1)
        response = client.post('/logout', data={'csrf_token': token})
        assert response.status_code == 302
        assert client.get('/home').status_code == 302
    finally:
        app.config['WTF_CSRF_ENABLED'] = False


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


def test_documentos_preservam_versoes_autor_historico_e_isolamento():
    client = app.test_client()
    login(client, 'cliente-a')
    with app.app_context():
        protocolo = Protocolo.query.filter_by(nome='Dado exclusivo A').one()
        protocolo_id = protocolo.id
    endpoint = f'/protocolo/{protocolo_id}/anexo/novo'
    def enviar(conteudo, documento_id=''):
        return client.post(endpoint, data={'documento_id': str(documento_id),
            'anexo': (io.BytesIO(conteudo), 'documento.txt')}, follow_redirects=True)
    assert enviar(b'primeira').status_code == 200
    with app.app_context():
        original = Anexo.query.filter_by(protocolo_id=protocolo_id).one()
        original_id, chave = original.id, original.documento_chave
    assert b'v2' in enviar(b'segunda', original_id).data
    assert b'v3' in enviar(b'terceira', original_id).data
    # Mesmo nome, mas documento independente, não deve se juntar ao anterior.
    enviar(b'independente')
    with app.app_context():
        versoes = Anexo.query.filter_by(documento_chave=chave).order_by(Anexo.versao).all()
        assert [a.versao for a in versoes] == [1, 2, 3]
        assert [a.file_data for a in versoes] == [b'primeira', b'segunda', b'terceira']
        assert all(a.enviado_por.login == 'admin' for a in versoes)
        assert Anexo.query.filter_by(protocolo_id=protocolo_id).count() == 4
        assert HistoricoProtocolo.query.filter_by(protocolo_id=protocolo_id, acao='NOVA_VERSAO_DOCUMENTO').count() == 2
    assert client.get(f'/anexo/{original_id}/download').data == b'primeira'
    client.post(f'/anexo/{original_id}/deletar')
    client.post(f'/protocolo/{protocolo_id}/deletar')
    assert client.get(f'/anexo/{original_id}/download').data == b'primeira'
    other = app.test_client()
    login(other, 'cliente-b')
    with app.app_context():
        outro_id = Protocolo.query.filter_by(nome='Dado exclusivo B').one().id
    response = other.post(f'/protocolo/{outro_id}/anexo/novo', data={
        'documento_id': str(original_id), 'anexo': (io.BytesIO(b'invasao'), 'arquivo.txt')})
    assert response.status_code == 404
    assert other.get(f'/anexo/{original_id}/download').status_code == 404


def test_upload_confere_conteudo_real_e_nao_apenas_extensao():
    with app.app_context():
        protocolo_id = Protocolo.query.filter_by(nome='Dado exclusivo A').one().id
        quantidade_inicial = Anexo.query.filter_by(protocolo_id=protocolo_id).count()
    client = app.test_client()
    login(client, 'cliente-a')
    endpoint = f'/protocolo/{protocolo_id}/anexo/novo'

    falso = client.post(endpoint, data={
        'anexo': (io.BytesIO(b'conteudo executavel disfarcado'), 'falso.pdf')
    }, follow_redirects=True)
    assert 'conteúdo do arquivo não corresponde' in falso.get_data(as_text=True)

    valido = client.post(endpoint, data={
        'anexo': (io.BytesIO(b'%PDF-1.4\n% teste seguro'), 'valido.pdf')
    }, follow_redirects=True)
    assert 'Documento enviado com sucesso' in valido.get_data(as_text=True)
    with app.app_context():
        assert Anexo.query.filter_by(protocolo_id=protocolo_id).count() == quantidade_inicial + 1


def test_versionamento_legado_nao_agrupa_documentos_distintos():
    client = app.test_client()
    login(client, 'cliente-a')
    with app.app_context():
        protocolo = Protocolo.query.filter_by(nome='Dado exclusivo A').one()
        protocolo_id = protocolo.id
        antigos = [Anexo(tenant_id=protocolo.tenant_id, protocolo_id=protocolo_id,
            file_name=f'legado-{i}.txt', storage_path='legado', file_size=3,
            mime_type='text/plain', file_data=b'old') for i in range(2)]
        db.session.add_all(antigos)
        db.session.commit()
        primeiro_id, segundo_id = [a.id for a in antigos]
    response = client.post(f'/protocolo/{protocolo_id}/anexo/novo', data={
        'documento_id': str(primeiro_id), 'anexo': (io.BytesIO(b'new'), 'revisao.txt')})
    assert response.status_code == 302
    with app.app_context():
        primeiro, segundo = db.session.get(Anexo, primeiro_id), db.session.get(Anexo, segundo_id)
        assert primeiro.documento_chave != segundo.documento_chave
        assert segundo.documento_chave == 'anexo'
        assert Anexo.query.filter_by(documento_chave=primeiro.documento_chave).count() == 2


def test_upload_vazio_e_processo_arquivado_nao_criam_versao():
    client = app.test_client()
    login(client, 'cliente-a')
    with app.app_context():
        protocolo = Protocolo.query.filter_by(nome='Dado exclusivo A').one()
        protocolo_id, quantidade = protocolo.id, Anexo.query.count()
    endpoint = f'/protocolo/{protocolo_id}/anexo/novo'
    assert client.post(endpoint, data={'anexo': (io.BytesIO(b''), 'vazio.txt')}).status_code == 302
    with app.app_context():
        assert Anexo.query.count() == quantidade
        protocolo = db.session.get(Protocolo, protocolo_id)
        protocolo.arquivado_em = datetime.utcnow()
        db.session.commit()
    try:
        assert client.post(endpoint, data={'anexo': (io.BytesIO(b'novo'), 'novo.txt')}).status_code == 302
        with app.app_context():
            assert Anexo.query.count() == quantidade
    finally:
        with app.app_context():
            db.session.get(Protocolo, protocolo_id).arquivado_em = None
            db.session.commit()


def test_listagem_relatorio_e_excel_usam_os_mesmos_filtros():
    client = app.test_client()
    login(client, 'cliente-a')
    with app.app_context():
        alvo = Protocolo.query.filter_by(nome='Dado exclusivo A').one()
        alvo.tipo_requerimento = 'Licença Especial'
        alvo.data_solicitacao = date(2026, 9, 3)
        db.session.add(Protocolo(tenant_id=alvo.tenant_id, numero='0099/2026',
            nome='Registro que deve ser excluído', tipo_requerimento='Outro',
            data_solicitacao=date(2026, 8, 1)))
        db.session.commit()
    filtros = '?nome=Dado+exclusivo+A&tipo=Licen%C3%A7a&data_inicio=2026-09-01&data_fim=2026-09-04'
    for endpoint in ['/protocolos', '/relatorios']:
        html = client.get(endpoint + filtros).get_data(as_text=True)
        assert 'Dado exclusivo A' in html
        assert 'Registro que deve ser excluído' not in html
    excel = client.get('/protocolos/backup/excel' + filtros)
    rows = list(load_workbook(io.BytesIO(excel.data)).active.iter_rows(values_only=True))
    assert len(rows) == 2 and rows[1][2] == 'Dado exclusivo A'
    assert client.get('/relatorios?data_inicio=2026-09-05&data_fim=2026-09-01').status_code == 400
    assert client.get('/protocolos?data_inicio=inválida').status_code == 400


def test_dashboard_controla_prazos_e_estatisticas_pelo_setor_atual():
    client = app.test_client()
    login(client, 'cliente-a')
    with app.app_context():
        protocolo = Protocolo.query.filter_by(nome='Dado exclusivo A').one()
        juridico = Lotacao.query.filter_by(nome='Jurídico').one()
        protocolo.setor_atual_id = juridico.id
        protocolo.prazo_em = date.today() - timedelta(days=1)
        protocolo.status = 'EM ANÁLISE'
        db.session.commit()
    dados = client.get('/protocolos/dashboard-stats?evolucaoPeriodo=all').get_json()
    assert dados['pendentesAntigos'] >= 1
    assert any(item['setor'] == 'Jurídico' and item['total'] >= 1 for item in dados['setorProtocolos'])
    filtrado = client.get('/protocolos/dashboard-stats?lotacao=Jur%C3%ADdico&evolucaoPeriodo=all').get_json()
    assert filtrado['statusProtocolos']
    assert all(item['setor'] == 'Jurídico' for item in filtrado['setorProtocolos'])
    with app.app_context():
        protocolo = Protocolo.query.filter_by(nome='Dado exclusivo A').one()
        protocolo.status = 'ARQUIVADO'
        db.session.commit()
    assert client.get('/protocolos/dashboard-stats?evolucaoPeriodo=all').get_json()['pendentesAntigos'] == 0


def test_situacao_de_prazo_filtra_listagem_relatorio_e_excel():
    client = app.test_client()
    login(client, 'cliente-a')
    with app.app_context():
        alvo = Protocolo.query.filter_by(nome='Dado exclusivo A').one()
        alvo.prazo_em = date.today() + timedelta(days=4)
        alvo.status = 'EM ANÁLISE'
        fora = Protocolo.query.filter_by(nome='Registro que deve ser excluído').one()
        fora.prazo_em = date.today() + timedelta(days=15)
        fora.status = 'EM ANÁLISE'
        db.session.commit()
    filtro = '?prazo=proximos_7'
    for endpoint in ['/protocolos', '/relatorios']:
        html = client.get(endpoint + filtro).get_data(as_text=True)
        assert 'Dado exclusivo A' in html
        assert 'Registro que deve ser excluído' not in html
    rows = list(load_workbook(io.BytesIO(client.get('/protocolos/backup/excel' + filtro).data))
                .active.iter_rows(values_only=True))
    assert rows[0][16] == 'Prazo'
    assert len(rows) == 2 and rows[1][2] == 'Dado exclusivo A'
    assert client.get('/protocolos?prazo=qualquer').status_code == 400


def test_administrador_edita_desativa_e_reativa_usuario_do_cliente():
    client = app.test_client()
    login(client, 'cliente-a')
    with app.app_context():
        consulta = Usuario.query.filter_by(tenant_id=1, login='consulta').one()
        juridico = Lotacao.query.filter_by(tenant_id=1, nome='Jurídico').one()
        consulta_id, juridico_id = consulta.id, juridico.id
    response = client.post(f'/admin/usuarios/{consulta_id}/editar', data={
        'nome_completo': 'Consulta Atualizada', 'email': 'consulta@example.test',
        'tipo': 'atendente', 'lotacao_id': juridico_id})
    assert response.status_code == 302
    with app.app_context():
        consulta = db.session.get(Usuario, consulta_id)
        assert (consulta.nome_completo, consulta.tipo, consulta.lotacao_id) == ('Consulta Atualizada', 'atendente', juridico_id)
    assert client.post(f'/admin/usuarios/{consulta_id}/status').status_code == 302
    inativo = app.test_client()
    response = inativo.post('/login', data={'organizacao': 'cliente-a', 'login': 'consulta', 'senha': 'senha-segura'}, follow_redirects=True)
    assert 'Não foi possível autenticar' in response.get_data(as_text=True)
    client.post(f'/admin/usuarios/{consulta_id}/status')
    assert b'Login bem-sucedido' in inativo.post('/login', data={
        'organizacao': 'cliente-a', 'login': 'consulta', 'senha': 'senha-segura'}, follow_redirects=True).data


def test_usuario_de_outro_cliente_e_proprio_admin_sao_protegidos():
    client = app.test_client()
    login(client, 'cliente-a')
    with app.app_context():
        admin_a = Usuario.query.filter_by(tenant_id=1, login='admin').one()
        admin_b = Usuario.query.filter_by(tenant_id=2, login='admin').one()
        admin_a_id, admin_b_id = admin_a.id, admin_b.id
    assert client.post(f'/admin/usuarios/{admin_b_id}/status').status_code == 404
    client.post(f'/admin/usuarios/{admin_a_id}/status')
    with app.app_context():
        assert db.session.get(Usuario, admin_a_id).status == 'ativo'
    client.post(f'/admin/usuarios/{admin_a_id}/editar', data={
        'nome_completo': 'Ana A', 'email': 'ana@example.test', 'tipo': 'consulta', 'lotacao_id': 0})
    with app.app_context():
        assert db.session.get(Usuario, admin_a_id).tipo == 'admin'


def test_numero_enviado_pelo_navegador_e_ignorado_e_criacao_e_atomica():
    client = app.test_client()
    login(client, 'cliente-a')
    response = client.post('/protocolo/novo', data={
        'numero': '9999/1999', 'nome': 'Numeração pelo servidor',
        'data_solicitacao': date.today().isoformat()}, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        protocolo = Protocolo.query.filter_by(nome='Numeração pelo servidor').one()
        assert protocolo.numero != '9999/1999'
        assert protocolo.numero.endswith(f'/{date.today().year}')
        assert HistoricoProtocolo.query.filter_by(protocolo_id=protocolo.id, acao='CRIACAO').count() == 1


def test_edicao_registra_campos_e_arquivado_fica_somente_leitura():
    client = app.test_client()
    login(client, 'cliente-a')
    with app.app_context():
        protocolo = Protocolo.query.filter_by(nome='Dado exclusivo A').one()
        protocolo_id = protocolo.id
    client.post(f'/protocolo/{protocolo_id}/editar', data={
        'nome': 'Nome revisado', 'data_solicitacao': date.today().isoformat(),
        'prazo_em': (date.today() + timedelta(days=3)).isoformat()})
    with app.app_context():
        evento = HistoricoProtocolo.query.filter_by(protocolo_id=protocolo_id, acao='EDICAO').order_by(HistoricoProtocolo.id.desc()).first()
        assert 'nome:' in evento.observacao and 'prazo:' in evento.observacao
        db.session.get(Protocolo, protocolo_id).arquivado_em = datetime.utcnow()
        db.session.commit()
    client.post(f'/protocolo/{protocolo_id}/editar', data={'nome': 'Alteração proibida'})
    with app.app_context():
        assert db.session.get(Protocolo, protocolo_id).nome == 'Nome revisado'
    resposta = client.post('/protocolos/atualizar', json={'protocoloId': protocolo_id, 'novoStatus': 'STATUS LIVRE'})
    assert resposta.status_code == 400


def test_arquivamento_exige_tramitacao_regularizada():
    client = app.test_client()
    login(client, 'cliente-a')
    with app.app_context():
        protocolo = Protocolo.query.filter_by(nome='Nome revisado').one()
        protocolo.arquivado_em = None
        juridico = Lotacao.query.filter_by(nome='Jurídico').one()
        protocolo_id, juridico_id = protocolo.id, juridico.id
        Movimentacao.query.filter_by(protocolo_id=protocolo_id).delete()
        db.session.commit()
    client.post(f'/protocolo/{protocolo_id}/tramitar', data={'setor_destino_id': juridico_id})
    client.post(f'/protocolo/{protocolo_id}/arquivar')
    with app.app_context():
        assert db.session.get(Protocolo, protocolo_id).arquivado_em is None
    client.post(f'/protocolo/{protocolo_id}/receber')
    client.post(f'/protocolo/{protocolo_id}/arquivar')
    with app.app_context():
        protocolo = db.session.get(Protocolo, protocolo_id)
        assert protocolo.arquivado_em is not None and protocolo.status == 'ARQUIVADO'


def test_dados_institucionais_sao_isolados_e_usados_no_pdf():
    client = app.test_client()
    login(client, 'cliente-a')
    response = client.post('/admin/identidade/logo', data={
        'municipio': 'Tabuleiro do Norte/CE', 'orgao': 'Gabinete da Prefeita',
        'rodape_documento': 'Praça da Matriz — Centro', 'salvar': 'Salvar logo'},
        follow_redirects=True)
    assert response.status_code == 200 and b'Dados institucionais atualizados' in response.data
    with app.app_context():
        a = Organizacao.query.filter_by(slug='cliente-a').one()
        b = Organizacao.query.filter_by(slug='cliente-b').one()
        protocolo_id = Protocolo.query.filter_by(tenant_id=a.id).first().id
        assert (a.municipio, a.orgao) == ('Tabuleiro do Norte/CE', 'Gabinete da Prefeita')
        assert b.municipio is None and b.orgao is None
    with app.test_request_context('/'):
        with app.app_context():
            protocolo = db.session.get(Protocolo, protocolo_id)
            organizacao = Organizacao.query.filter_by(slug='cliente-a').one()
            modelo = render_template('pdf_template.html', protocolo=protocolo,
                                     organizacao=organizacao, pdf_logo_url='/logo.png')
            assert 'Gabinete da Prefeita' in modelo and 'Praça da Matriz' in modelo
            assert 'Secretaria da Administração' not in modelo
    html = client.get(f'/protocolo/{protocolo_id}').get_data(as_text=True)
    assert 'data-organization-office="Gabinete da Prefeita"' in html
    assert 'static/img/rodape.jpg' not in html


def test_pdf_gerado_e_armazenado_com_versionamento_e_historico():
    class FakeHTML:
        def __init__(self, string, base_url):
            self.string = string
        def write_pdf(self):
            return b'%PDF-1.7\nconteudo de teste'
    client = app.test_client()
    login(client, 'cliente-a')
    with app.app_context():
        protocolo = Protocolo.query.filter_by(tenant_id=1, arquivado_em=None).first()
        protocolo_id = protocolo.id
    with patch.dict(sys.modules, {'weasyprint': types.SimpleNamespace(HTML=FakeHTML)}):
        primeira = client.post(f'/protocolo/{protocolo_id}/documento/gerar')
        segunda = client.post(f'/protocolo/{protocolo_id}/documento/gerar')
    assert primeira.status_code == 200 and primeira.content_type == 'application/pdf'
    assert segunda.status_code == 200 and '_v2.pdf' in segunda.headers['Content-Disposition']
    with app.app_context():
        docs = Anexo.query.filter_by(protocolo_id=protocolo_id, documento_chave='documento-protocolo').order_by(Anexo.versao).all()
        assert [documento.versao for documento in docs] == [1, 2]
        assert all(documento.file_data.startswith(b'%PDF') for documento in docs)
        assert HistoricoProtocolo.query.filter_by(protocolo_id=protocolo_id, acao='DOCUMENTO_GERADO').count() == 2
    with app.app_context():
        protocolo = db.session.get(Protocolo, protocolo_id)
        protocolo.arquivado_em = datetime.utcnow()
        db.session.commit()
    with patch.dict(sys.modules, {'weasyprint': types.SimpleNamespace(HTML=FakeHTML)}):
        assert client.post(f'/protocolo/{protocolo_id}/documento/gerar').status_code == 302
    with app.app_context():
        assert Anexo.query.filter_by(protocolo_id=protocolo_id, documento_chave='documento-protocolo').count() == 2
