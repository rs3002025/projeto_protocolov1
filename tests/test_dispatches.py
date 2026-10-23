"""Testes isolados: nunca usam bancos nem usuários de clientes."""
import os
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

os.environ['SECRET_KEY'] = 'isolated-dispatch-test-key'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['TENANT_SUBDOMAINS_ENABLED'] = 'false'
from app import app, db, verify_audit_chain, history_parts
from models import (Organizacao, Usuario, Protocolo, HistoricoProtocolo,
                    DespachoProtocolo, Lotacao, Movimentacao, Servidor, PortalSessao, TipoRequerimento)


class DispatchTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        with app.app_context():
            assert db.engine.url.drivername == 'sqlite'
            # Outras suítes podem remover a pasta do SQLite compartilhado.
            database = db.engine.url.database
            if database and database != ':memory:':
                Path(database).parent.mkdir(parents=True, exist_ok=True)
            db.drop_all()
            db.create_all()
            a, b = Organizacao(nome='Cliente fictício A', slug='teste-a'), Organizacao(nome='Cliente fictício B', slug='teste-b')
            db.session.add_all([a, b]); db.session.flush()
            self.tenant, self.other = a.id, b.id
            s = Lotacao(tenant_id=a.id, nome='Secretaria de teste')
            t = Lotacao(tenant_id=a.id, nome='Outro setor')
            db.session.add_all([s, t]); db.session.flush()
            self.sector, self.other_sector = s.id, t.id
            self.users, self.ids = {}, {}
            for role in ('admin', 'protocolista', 'tramitador', 'consulta', 'requerente'):
                u = Usuario(tenant_id=a.id, nome=role, nome_completo='Nome ' + role,
                            login=role, senha='not-a-real-credential', tipo=role,
                            lotacao_id=s.id if role == 'tramitador' else None)
                db.session.add(u); db.session.flush()
                self.users[role], self.ids[role] = u.get_id(), u.id
            p = Protocolo(tenant_id=a.id, numero='0001/2026', nome='Requerente fictício',
                          status='EM ANÁLISE', responsavel='protocolista', setor_atual_id=s.id,
                          observacoes='Informação opcional')
            foreign = Protocolo(tenant_id=b.id, numero='0001/2026', nome='Outro cliente', status='EM ANÁLISE')
            db.session.add_all([p, foreign]); db.session.commit()
            self.pid, self.foreign = p.id, foreign.id
        self.client = app.test_client()
        self.pdf_mock = patch('protocol_dispatches.render_dispatch_pdf', return_value=b'%PDF-1.7\nfictitious-test-only')
        self.renderer = self.pdf_mock.start()
        self.bucket_mock = patch('app.bucket_client', return_value=None)
        self.bucket_mock.start()

    def tearDown(self):
        self.pdf_mock.stop(); self.bucket_mock.stop()
        app.config['WTF_CSRF_ENABLED'] = False
        with app.app_context():
            db.session.remove(); db.drop_all()

    def login(self, role):
        with self.client.session_transaction() as s:
            s.clear(); s['_user_id'] = self.users[role]; s['_fresh'] = True

    def post(self, text='Manifestação formal.\n\nSegundo parágrafo.', token='a' * 32, pid=None):
        return self.client.post(f'/protocolo/{pid or self.pid}/despachos', data={'texto': text, 'envio_token': token})

    def count(self):
        with app.app_context():
            return DespachoProtocolo.query.count()

    def test_roles_register_and_audit(self):
        for i, role in enumerate(('admin', 'protocolista', 'tramitador')):
            self.login(role)
            r = self.post(token=str(i) * 32)
            self.assertEqual(r.status_code, 302)
            self.assertTrue(r.location.endswith('#despachos'))
        with app.app_context():
            records = DespachoProtocolo.query.order_by(DespachoProtocolo.numero).all()
            self.assertEqual([d.numero for d in records], [1, 2, 3])
            self.assertEqual(records[2].autor_nome, 'Nome tramitador')
            self.assertEqual(records[2].autor_setor, 'Secretaria de teste')
            self.assertIn('\n\n', records[0].texto)
            self.assertEqual(HistoricoProtocolo.query.filter_by(acao='DESPACHO_REGISTRADO').count(), 3)
            self.assertTrue(verify_audit_chain(self.tenant)[0])
            self.assertEqual(db.session.get(Protocolo, self.pid).status, 'EM ANÁLISE')

    def test_duplicate_submission(self):
        self.login('admin'); self.post(); self.post()
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.renderer.call_count, 1)

    def delete_dispatch(self, did, **changes):
        data={'confirmar_exclusao': '1', 'motivo': 'Lançamento de teste'}
        data.update(changes)
        return self.client.post(f'/protocolo/{self.pid}/despachos/{did}/excluir', data=data)

    def test_admin_deletes_dispatch_preserving_evidence_and_sequence(self):
        self.login('admin'); self.post('Despacho que será excluído.')
        with app.app_context():
            d=DespachoProtocolo.query.one(); did=d.id; pdf=d.file_data
        self.assertEqual(self.delete_dispatch(did).status_code, 302)
        html=self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True)
        self.assertNotIn('Despacho que será excluído.', html)
        self.assertNotIn(f'id="despacho-{did}"', html)
        self.assertIn('Nenhum despacho registrado', html)
        self.assertEqual(self.client.get(f'/protocolo/{self.pid}/despachos/{did}/pdf').status_code, 404)
        self.assertEqual(self.delete_dispatch(did).status_code, 404)
        self.post('Novo despacho.', token='b'*32)
        with app.app_context():
            deleted=db.session.get(DespachoProtocolo,did)
            self.assertIsNotNone(deleted.excluido_em)
            self.assertEqual(deleted.excluido_por_id,self.ids['admin'])
            self.assertEqual(deleted.file_data,pdf)
            self.assertEqual(deleted.texto,'Despacho que será excluído.')
            self.assertEqual([d.numero for d in DespachoProtocolo.query.order_by(DespachoProtocolo.numero)],[1,2])
            self.assertEqual(HistoricoProtocolo.query.filter_by(acao='DESPACHO_EXCLUIDO').count(),1)
            self.assertTrue(verify_audit_chain(self.tenant)[0])

    def test_dispatch_delete_admin_only_confirmed_csrf_and_tenant_scoped(self):
        self.login('admin'); self.post()
        with app.app_context(): did=DespachoProtocolo.query.one().id
        for role in ('protocolista','tramitador','consulta','requerente'):
            self.login(role)
            self.assertIn(self.delete_dispatch(did).status_code,(302,403))
            html=self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True)
            self.assertNotIn('>Excluir despacho<',html)
        self.login('admin')
        self.assertEqual(self.client.get(f'/protocolo/{self.pid}/despachos/{did}/excluir').status_code,405)
        self.assertEqual(self.delete_dispatch(did, confirmar_exclusao='').status_code,400)
        self.assertEqual(self.delete_dispatch(did, motivo='x'*2001).status_code,400)
        self.assertEqual(self.delete_dispatch(did, motivo='bad\x00value').status_code,400)
        self.assertEqual(self.client.post(f'/protocolo/{self.foreign}/despachos/{did}/excluir', data={'confirmar_exclusao':'1'}).status_code,404)
        app.config['WTF_CSRF_ENABLED']=True
        self.assertEqual(self.delete_dispatch(did).status_code,400)
        app.config['WTF_CSRF_ENABLED']=False
        with app.app_context(): self.assertIsNone(db.session.get(DespachoProtocolo,did).excluido_em)

    def test_attachment_replace_is_per_current_file_and_preserves_versions(self):
        import io
        from models import Anexo
        self.login('admin')
        endpoint=f'/protocolo/{self.pid}/anexo/novo'
        self.assertEqual(self.client.post(endpoint,data={'anexo':(io.BytesIO(b'original'),'teste.txt')}).status_code,302)
        with app.app_context(): original=Anexo.query.one().id
        html=self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True)
        self.assertNotIn('Novo documento independente',html)
        self.assertNotIn('<select name="documento_id"',html)
        self.assertIn(f'name="documento_id" value="{original}"',html)
        self.assertIn('>Substituir<',html)
        self.assertEqual(self.client.post(endpoint,data={'documento_id':str(original),'anexo':(io.BytesIO(b'replacement'),'novo.txt')}).status_code,302)
        with app.app_context():
            versions=Anexo.query.order_by(Anexo.versao).all()
            self.assertEqual([a.file_data for a in versions],[b'original',b'replacement'])
            latest=versions[-1].id
        html=self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True)
        self.assertNotIn(f'name="documento_id" value="{original}"',html)
        self.assertIn(f'name="documento_id" value="{latest}"',html)
        self.login('consulta')
        html=self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True)
        self.assertNotIn('>Substituir<',html)

    def test_read_only_and_portal_cannot_register(self):
        for role in ('consulta', 'requerente'):
            self.login(role)
            self.assertIn(self.post().status_code, (302, 403))
        self.assertEqual(self.count(), 0)

    def test_tenant_isolation_create_and_download(self):
        self.login('admin')
        self.assertEqual(self.post(pid=self.foreign).status_code, 404)
        self.post()
        with app.app_context():
            did = DespachoProtocolo.query.one().id
        self.assertEqual(self.client.get(f'/protocolo/{self.foreign}/despachos/{did}/pdf').status_code, 404)

    def test_other_sector_and_nominal_recipient(self):
        self.login('tramitador')
        with app.app_context():
            p = db.session.get(Protocolo, self.pid)
            p.setor_atual_id = self.other_sector
            # Participante pode consultar, mas não despachar fora da custódia.
            db.session.add(Movimentacao(tenant_id=self.tenant, protocolo_id=p.id,
                setor_origem_id=self.sector, setor_destino_id=self.other_sector,
                enviado_por_id=self.ids['tramitador'], recebido_em=datetime.now()))
            db.session.commit()
        self.assertEqual(self.post().status_code, 403)
        with app.app_context():
            p = db.session.get(Protocolo, self.pid); p.setor_atual_id = self.sector
            db.session.add(Movimentacao(tenant_id=self.tenant, protocolo_id=p.id,
                setor_origem_id=self.sector, setor_destino_id=self.sector,
                destinatario_usuario_id=self.ids['protocolista'],
                enviado_por_id=self.ids['tramitador'], recebido_em=datetime.now()))
            db.session.commit()
        self.assertEqual(self.post().status_code, 403)
        self.assertEqual(self.count(), 0)

    def test_archived_and_pending_cannot_add(self):
        self.login('admin')
        with app.app_context():
            db.session.get(Protocolo, self.pid).status = 'ARQUIVADO'; db.session.commit()
        self.assertEqual(self.post().status_code, 409)
        with app.app_context():
            p = db.session.get(Protocolo, self.pid); p.status = 'EM TRAMITAÇÃO'
            db.session.add(Movimentacao(tenant_id=self.tenant, protocolo_id=p.id,
                setor_destino_id=self.sector, enviado_por_id=self.ids['admin']))
            db.session.commit()
        self.assertEqual(self.post().status_code, 409)
        self.assertEqual(self.count(), 0)

    def test_input_validation_and_long_text(self):
        self.login('admin')
        for text in ('', '  ', 'x' * 100001, 'abc\x00def'):
            self.assertEqual(self.post(text).status_code, 400)
        self.assertEqual(self.post(token='bad').status_code, 400)
        self.assertEqual(self.post('Texto longo.\n' * 7000).status_code, 302)
        self.assertEqual(self.count(), 1)

    def test_csrf_and_get_method(self):
        self.login('admin')
        app.config['WTF_CSRF_ENABLED'] = True
        self.assertEqual(self.post().status_code, 400)
        app.config['WTF_CSRF_ENABLED'] = False
        self.assertEqual(self.client.get(f'/protocolo/{self.pid}/despachos').status_code, 405)
        self.assertEqual(self.count(), 0)

    def test_pdf_snapshot_integrity_and_download(self):
        self.login('protocolista'); self.post()
        with app.app_context():
            d = DespachoProtocolo.query.one(); did = d.id; original = d.file_data
            db.session.get(Usuario, self.ids['protocolista']).nome_completo = 'Nome alterado'
            db.session.commit()
            self.assertEqual(d.autor_nome, 'Nome protocolista')
        self.login('consulta')
        r = self.client.get(f'/protocolo/{self.pid}/despachos/{did}/pdf')
        self.assertEqual(r.status_code, 200); self.assertEqual(r.data, original)
        self.assertIn('attachment;', r.headers['Content-Disposition'])
        self.assertEqual(self.renderer.call_count, 1)
        with app.app_context():
            DespachoProtocolo.query.one().file_data = b'altered'; db.session.commit()
        self.assertEqual(self.client.get(f'/protocolo/{self.pid}/despachos/{did}/pdf').status_code, 503)

    def test_renderer_failure_preserves_text_and_creates_nothing(self):
        self.login('admin'); self.renderer.side_effect = RuntimeError('test failure')
        r = self.post('Texto que não deve ser perdido.')
        self.assertEqual(r.status_code, 503)
        self.assertIn('Texto que não deve ser perdido.', r.get_data(as_text=True))
        self.assertEqual(self.count(), 0)

    def test_page_escapes_text_and_labels(self):
        self.login('admin'); self.post('<script>alert(1)</script>')
        html = self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('Informações adicionais', html)
        self.assertIn('Nome protocolista', html)
        self.assertNotIn('>Visão geral</h2>', html)
        self.login('consulta')
        html = self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True)
        self.assertNotIn('name="envio_token"', html)
        self.assertNotIn('use Retificar', html)

    def test_history_separation_preserves_original(self):
        h = HistoricoProtocolo(acao='TRAMITACAO', observacao='Encaminhado para SEAD, disponível a todos do setor. Minha observação.\nOutra linha.')
        parts = history_parts(h)
        self.assertEqual(parts['sistema'], 'Encaminhado para SEAD, disponível a todos do setor.')
        self.assertEqual(parts['observacao'], 'Minha observação.\nOutra linha.')
        self.assertIn('Minha observação.', h.observacao)

    def test_schema_bootstrap_is_idempotent(self):
        from bootstrap_db import bootstrap
        bootstrap(); bootstrap()
        self.assertEqual(self.count(), 0)
        with app.app_context():
            self.assertEqual(db.session.get(Protocolo, self.pid).numero, '0001/2026')

    def portal_login(self):
        from app import _portal_token_hash
        with app.app_context():
            db.session.get(Organizacao, self.tenant).portal_servidor_remoto_enabled = True
            s = Servidor(tenant_id=self.tenant, nome='Servidor fictício', matricula='000002')
            db.session.add(s); db.session.flush()
            db.session.get(Usuario, self.ids['requerente']).servidor_id = s.id
            db.session.add(TipoRequerimento(tenant_id=self.tenant, nome='Tipo fictício', ativo=True))
            db.session.add(PortalSessao(tenant_id=self.tenant, usuario_id=self.ids['requerente'],
                identificador_hash=_portal_token_hash('fictitious-session'), dispositivo='Teste isolado',
                expira_em=datetime.now(timezone.utc) + timedelta(hours=1)))
            db.session.commit()
        self.login('requerente')
        with self.client.session_transaction() as s:
            s['auth_surface'] = 'portal'; s['portal_session_token'] = 'fictitious-session'

    def test_portal_additional_information_is_optional(self):
        self.portal_login()
        with patch('app.render_protocol_pdf', return_value=b'%PDF-fictitious-only'), patch('app.gerar_proximo_numero_protocolo', return_value='0099/2026'):
            r = self.client.post('/portal/novo', data={'tipo_requerimento': 'Tipo fictício', 'declaracao': 'on', 'observacoes': ''})
        self.assertEqual(r.status_code, 302)
        with app.app_context():
            p = Protocolo.query.filter_by(tenant_id=self.tenant, numero='0099/2026').one()
            self.assertFalse(p.observacoes)
            self.assertEqual(p.modalidade_abertura, 'remota_requerente')
            self.assertTrue(verify_audit_chain(self.tenant)[0])
        denied = self.client.get(f'/protocolo/{self.pid}/despachos/1/pdf')
        self.assertEqual(denied.status_code, 302)
        self.assertIn('/portal', denied.location)

    def test_portal_still_requires_type_and_declaration(self):
        self.portal_login()
        for data in ({'tipo_requerimento': 'Tipo fictício'}, {'declaracao': 'on'}):
            self.assertEqual(self.client.post('/portal/novo', data=data).status_code, 400)

    def test_nominal_destination_must_be_an_internal_operator(self):
        self.login('admin')
        with app.app_context():
            db.session.get(Usuario, self.ids['consulta']).lotacao_id = self.sector
            db.session.commit()
        r = self.client.post(f'/protocolo/{self.pid}/tramitar', data={'setor_destino_id': self.sector, 'destinatario_usuario_id': self.ids['consulta']})
        self.assertEqual(r.status_code, 404)

    def test_anonymous_cannot_create_or_download(self):
        self.assertEqual(self.post().status_code, 302)
        self.assertEqual(self.client.get(f'/protocolo/{self.pid}/despachos/1/pdf').status_code, 302)
        self.assertEqual(self.count(), 0)

    def test_optional_information_template_has_no_required(self):
        self.portal_login()
        html = self.client.get('/portal/novo').get_data(as_text=True)
        import re
        field = re.search(r'<textarea\b[^>]*name="observacoes"[^>]*>', html).group(0)
        self.assertNotRegex(field, r'\brequired\b')
        self.assertIn('Informações adicionais (opcional)', html)

    def test_actions_are_not_duplicated_in_content(self):
        self.login('admin')
        html = self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True)
        documents = html.split('id="documentos"', 1)[1].split('id="historico"', 1)[0]
        routing = html.split('id="tramitacao"', 1)[1].split('id="despachos"', 1)[0]
        self.assertNotIn('>Abrir requerimento<', documents)
        self.assertNotIn('>Arquivar processo<', routing)
        self.assertIn('data-bs-target="#modalArquivarProtocolo"', html)
        self.assertIn('dispatch-document-header', html if self.count() else self._page_with_dispatch())

    def _page_with_dispatch(self):
        self.post()
        return self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True)

    @unittest.skipUnless(os.environ.get('RUN_PDF_QA') == '1', 'Exige o renderizador PDF e suas bibliotecas nativas.')
    def test_real_pdf_renderer(self):
        self.pdf_mock.stop()
        from protocol_dispatches import render_dispatch_pdf
        from io import BytesIO
        from PIL import Image
        with app.app_context(), app.test_request_context('/'):
            org = db.session.get(Organizacao, self.tenant)
            stream = BytesIO(); Image.new('RGB', (16, 16), 'green').save(stream, format='PNG')
            org.logo_data = stream.getvalue()
            d = DespachoProtocolo(numero=1, protocolo_numero='0001/2026', texto='<img src="http://127.0.0.1/private">\n\nTexto formal com acentuação e parágrafos.', autor_nome='Autor fictício', autor_setor='Setor fictício', criado_em=datetime.now(timezone.utc))
            with patch('urllib.request.HTTPHandler.http_open', side_effect=AssertionError('Não deve acessar a rede')):
                data = render_dispatch_pdf(d, org)
            self.assertTrue(data.startswith(b'%PDF-'))
            self.assertGreater(len(data), 5000)

    def test_pdf_header_number_and_optional_author_units(self):
        from types import SimpleNamespace
        from flask import render_template
        with app.app_context(), app.test_request_context('/'):
            org = db.session.get(Organizacao, self.tenant)
            d = SimpleNamespace(numero=2, protocolo_numero='0001/2026', texto='Texto fictício',
                autor_nome='Autor fictício', autor_setor='Setor de atendimento',
                autor_secretaria='Secretaria de Administração', criado_em=datetime.now(timezone.utc))
            html = render_template('despacho_pdf.html', despacho=d, organizacao=org, pdf_logo_url=None)
            self.assertIn('DESPACHO 002 - PROTOCOLO 0001/2026', html)
            header = html.split('<header>', 1)[1].split('</header>', 1)[0]
            self.assertIn('Secretaria de Administração', header)
            self.assertIn('Setor de atendimento', header)
            self.assertNotIn(org.nome, header)
            d.autor_setor = d.autor_secretaria
            html = render_template('despacho_pdf.html', despacho=d, organizacao=org, pdf_logo_url=None)
            self.assertEqual(html.split('<header>', 1)[1].split('</header>', 1)[0].count(d.autor_secretaria), 1)
            del d.autor_secretaria
            d.autor_setor = None
            d.numero = 1001
            html = render_template('despacho_pdf.html', despacho=d, organizacao=org, pdf_logo_url=None)
            self.assertIn('DESPACHO 1001 - PROTOCOLO 0001/2026', html)
            self.assertNotIn('None', html.split('<header>', 1)[1].split('</header>', 1)[0])


if __name__ == '__main__':
    unittest.main()
