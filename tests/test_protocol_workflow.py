"""Testes sem conexão a bancos reais: participação, autorização e ciclo de vida."""
import os
import unittest
from pathlib import Path
from sqlalchemy import inspect, text

os.environ['SECRET_KEY'] = 'isolated-workflow-test-key'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['TENANT_SUBDOMAINS_ENABLED'] = 'false'
from app import app, db, verify_audit_chain
from models import (Organizacao, Usuario, Lotacao, Protocolo, Movimentacao,
                    ProvidenciaProtocolo, AcompanhamentoProtocolo, HistoricoProtocolo,
                    SolicitacaoComplemento, Anexo)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        with app.app_context():
            assert db.engine.url.drivername == 'sqlite'
            if db.engine.url.database not in (None, ':memory:'):
                Path(db.engine.url.database).parent.mkdir(parents=True, exist_ok=True)
            db.drop_all(); db.create_all()
            a, b = Organizacao(nome='Fictício A', slug='a'), Organizacao(nome='Fictício B', slug='b')
            db.session.add_all([a, b]); db.session.flush()
            self.tenant, self.foreign_tenant = a.id, b.id
            s, t = Lotacao(tenant_id=a.id, nome='SEFIN'), Lotacao(tenant_id=a.id, nome='SEPLAG')
            db.session.add_all([s, t]); db.session.flush()
            self.sector = s.id
            self.users, self.ids = {}, {}
            for login, role, sector in [('admin', 'admin', s.id), ('protocolista', 'protocolista', s.id),
                    ('alice', 'tramitador', s.id), ('bob', 'tramitador', s.id),
                    ('carol', 'tramitador', t.id), ('consulta', 'consulta', s.id), ('foreign', 'tramitador', None)]:
                u = Usuario(tenant_id=b.id if login == 'foreign' else a.id, nome=login, login=login,
                            senha='not-a-real-credential', tipo=role, lotacao_id=sector)
                db.session.add(u); db.session.flush()
                self.users[login], self.ids[login] = u.get_id(), u.id
            p = Protocolo(tenant_id=a.id, numero='0001/2026', nome='Requerente fictício',
                          status='EM ANÁLISE', responsavel='protocolista', setor_atual_id=s.id)
            q = Protocolo(tenant_id=b.id, numero='0001/2026', nome='Outro cliente', status='EM ANÁLISE')
            db.session.add_all([p, q]); db.session.commit()
            self.pid, self.foreign_pid = p.id, q.id
        self.client = app.test_client()

    def tearDown(self):
        with app.app_context():
            db.session.remove(); db.drop_all()

    def login(self, who):
        with self.client.session_transaction() as s:
            s['_user_id'], s['_fresh'] = self.users[who], True

    def post(self, action, data=None):
        if action == 'excluir':
            data = data or {}
            action, data = 'deletar', {'justificativa': data.get('motivo', ''),
                'confirmar_exclusao': '1' if data.get('confirmacao') == '0001/2026' else ''}
        return self.client.post(f'/protocolo/{self.pid}/{action}', data=data or {})

    def send(self, *names, **extra):
        return self.post('tramitar', {'destinatarios_ids': [str(self.ids[n]) for n in names], **extra})

    def participation(self, name):
        with app.app_context():
            m = Movimentacao.query.filter_by(protocolo_id=self.pid, destinatario_usuario_id=self.ids[name]).order_by(Movimentacao.id.desc()).first()
            return m.providencia_id, m.id

    def receive(self, name):
        self.login(name)
        _, mid = self.participation(name)
        return self.post('receber', {'movimentacao_id': mid})

    def test_single_and_transfer_have_one_participation(self):
        self.login('protocolista')
        self.assertEqual(self.post('tramitar', {'setor_destino_id': self.sector, 'destinatario_usuario_id': self.ids['alice']}).status_code, 302)
        self.assertEqual(self.receive('alice').status_code, 302)
        pid, _ = self.participation('alice')
        self.assertEqual(self.send('carol', providencia_id=pid).status_code, 302)
        self.assertEqual(self.send('bob', providencia_id=pid).status_code, 403)
        self.assertEqual(self.receive('carol').status_code, 302)
        with app.app_context():
            self.assertEqual(ProvidenciaProtocolo.query.count(), 1)
            self.assertEqual(db.session.get(Protocolo, self.pid).responsavel, 'carol')
            self.assertTrue(verify_audit_chain(self.tenant)[0])

    def test_parallel_completion_is_not_administrative_finalization(self):
        self.login('protocolista'); self.assertEqual(self.send('alice', 'bob').status_code, 302)
        self.assertEqual(self.receive('alice').status_code, 302)
        alice, _ = self.participation('alice')
        # Alice pode despachar enquanto Bob ainda não recebeu.
        html = self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True)
        self.assertIn('Incluir despacho', html)
        self.assertEqual(self.post(f'providencia/{alice}/concluir', {'resultado': 'Parecer favorável.'}).status_code, 302)
        self.login('admin'); self.assertEqual(self.post('finalizar').status_code, 409)
        self.assertEqual(self.receive('bob').status_code, 302)
        bob, _ = self.participation('bob')
        self.assertEqual(self.post(f'providencia/{bob}/concluir').status_code, 302)
        with app.app_context():
            self.assertNotIn(db.session.get(Protocolo, self.pid).status, ('FINALIZADO', 'CONCLUÍDO'))
        self.login('admin'); self.assertEqual(self.post('finalizar', {'resultado': 'Deferido.'}).status_code, 302)
        self.post('finalizar')
        with app.app_context():
            p = db.session.get(Protocolo, self.pid)
            self.assertEqual(p.status, 'CONCLUÍDO'); self.assertEqual(p.resultado_final, 'Deferido.')
            self.assertEqual(HistoricoProtocolo.query.filter_by(acao='FINALIZACAO').count(), 1)
            self.assertTrue(verify_audit_chain(self.tenant)[0])
        self.assertEqual(self.send('carol', nova_providencia='1').status_code, 409)
        self.assertNotIn('href="#tramitacao"', self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True))
        self.assertIn('protocol-number-finalized', self.client.get('/protocolos').get_data(as_text=True))

    def test_nominal_reception_and_completion_cannot_be_stolen(self):
        self.login('admin'); self.send('alice', 'carol')
        aid, mid = self.participation('alice')
        self.login('bob')
        self.assertEqual(self.post('receber', {'movimentacao_id': mid}).status_code, 403)
        self.assertEqual(self.post(f'providencia/{aid}/concluir').status_code, 403)
        self.receive('alice')
        self.login('bob'); self.assertEqual(self.send('carol', providencia_id=aid).status_code, 403)

    def test_watching_is_per_user_idempotent_and_survives_transfer(self):
        self.login('protocolista')
        for _ in range(2): self.assertEqual(self.post('acompanhar', {'acompanhar': '1'}).status_code, 302)
        self.send('alice'); self.receive('alice')
        self.login('protocolista')
        self.assertIn('0001/2026', self.client.get('/meus_protocolos').get_data(as_text=True))
        self.post('acompanhar', {'acompanhar': '0'})
        self.assertNotIn('0001/2026', self.client.get('/meus_protocolos').get_data(as_text=True))
        with app.app_context(): self.assertEqual(AcompanhamentoProtocolo.query.count(), 0)
        self.login('alice'); self.assertIn('0001/2026', self.client.get('/meus_protocolos').get_data(as_text=True))

    def test_delete_is_admin_only_preserves_records_and_blocks_access(self):
        with app.app_context():
            db.session.add(Anexo(tenant_id=self.tenant, protocolo_id=self.pid, file_name='ficticio.txt', storage_path='isolated', file_size=8, mime_type='text/plain', file_data=b'ficticio'))
            db.session.commit(); aid = Anexo.query.first().id
            token = db.session.get(Protocolo, self.pid).consulta_token
        for role in ('protocolista', 'alice', 'consulta'):
            self.login(role); self.post('excluir', {'confirmacao': '0001/2026', 'motivo': 'Teste isolado'})
            with app.app_context(): self.assertIsNone(db.session.get(Protocolo, self.pid).excluido_em)
        self.login('admin'); self.assertEqual(self.post('excluir').status_code, 400)
        self.assertEqual(self.post('excluir', {'confirmacao': '0001/2026', 'motivo': 'Cadastro duplicado fictício'}).status_code, 302)
        self.assertEqual(self.client.get(f'/protocolo/{self.pid}').status_code, 404)
        self.assertEqual(self.client.get(f'/consulta/{token}').status_code, 404)
        self.assertEqual(self.client.get(f'/anexo/{aid}/download').status_code, 404)
        self.assertNotIn('0001/2026', self.client.get('/protocolos').get_data(as_text=True))
        with app.app_context():
            self.assertEqual(Anexo.query.count(), 1)
            self.assertIsNotNone(db.session.get(Protocolo, self.pid).excluido_em)
            self.assertTrue(verify_audit_chain(self.tenant)[0])

    def test_foreign_targets_fail_atomically_and_other_client_is_inaccessible(self):
        self.login('admin'); self.assertEqual(self.send('alice', 'foreign').status_code, 404)
        with app.app_context(): self.assertEqual(Movimentacao.query.count(), 0)
        for endpoint in ('tramitar', 'receber', 'finalizar', 'deletar', 'acompanhar'):
            r = self.client.post(f'/protocolo/{self.foreign_pid}/{endpoint}', data={'acompanhar': '1'})
            self.assertEqual(r.status_code, 404)

    def test_admin_only_finalization_and_legacy_status_cannot_bypass(self):
        self.login('protocolista'); self.post('finalizar')
        with app.app_context(): self.assertNotEqual(db.session.get(Protocolo, self.pid).status, 'FINALIZADO')
        self.login('admin')
        r = self.client.post('/protocolos/atualizar', json={'protocoloId': self.pid, 'novoStatus': 'FINALIZADO'})
        self.assertEqual(r.status_code, 400)

    def test_post_csrf_and_confirmation(self):
        self.login('admin')
        self.assertEqual(self.client.get(f'/protocolo/{self.pid}/finalizar').status_code, 405)
        app.config['WTF_CSRF_ENABLED'] = True
        try:
            for action in ('finalizar', 'excluir', 'acompanhar', 'tramitar', 'receber'):
                self.assertEqual(self.post(action).status_code, 400)
        finally: app.config['WTF_CSRF_ENABLED'] = False

    def test_view_renders_new_actions_and_parallel_responsibilities(self):
        self.login('admin'); self.send('alice', 'carol')
        html = self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True)
        for label in ('Acompanhar processo', 'Concluir processo', 'Excluir protocolo', 'Providência 1', 'Providência 2', 'Receber participação'):
            self.assertIn(label, html)
        self.login('consulta'); html = self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True)
        self.assertNotIn('id="excluir-processo"', html)


    def test_duplicate_submission_token_is_not_sent_twice(self):
        self.login('admin')
        token = 'ficticio-encaminhamento-idempotente'
        self.assertEqual(self.send('alice', 'bob', envio_token=token).status_code, 302)
        self.assertEqual(self.send('alice', 'bob', envio_token=token).status_code, 302)
        with app.app_context():
            self.assertEqual(Movimentacao.query.count(), 2)
            self.assertEqual(ProvidenciaProtocolo.query.count(), 2)

    def test_parallel_transfer_does_not_remove_other_holder(self):
        self.login('protocolista'); self.send('alice', 'bob')
        self.receive('alice'); aid, _ = self.participation('alice')
        self.receive('bob')
        self.login('alice'); self.assertEqual(self.send('carol', providencia_id=aid).status_code, 302)
        self.login('bob'); bid, _ = self.participation('bob')
        self.assertEqual(self.post(f'providencia/{bid}/concluir').status_code, 302)
        self.assertEqual(self.receive('carol').status_code, 302)
        with app.app_context():
            self.assertEqual(ProvidenciaProtocolo.query.count(), 2)
            self.assertIsNone(db.session.get(ProvidenciaProtocolo, aid).concluida_em)
            self.assertTrue(verify_audit_chain(self.tenant)[0])

    def test_pending_complement_prevents_finalization(self):
        with app.app_context():
            db.session.add(SolicitacaoComplemento(tenant_id=self.tenant, protocolo_id=self.pid,
                solicitado_por_id=self.ids['admin'], motivo='Documento complementar fictício', status='PENDENTE'))
            db.session.commit()
        self.login('admin'); self.assertEqual(self.post('finalizar').status_code, 409)

    def test_only_admin_and_protocolista_can_follow(self):
        for role in ('alice', 'bob', 'consulta'):
            self.login(role)
            self.post('acompanhar', {'acompanhar': '1'})
        with app.app_context(): self.assertEqual(AcompanhamentoProtocolo.query.count(), 0)

    def test_invalid_text_does_not_write_partial_actions(self):
        self.login('admin')
        self.assertEqual(self.send('alice', observacao='Teste\x00inválido').status_code, 400)
        self.assertEqual(self.post('finalizar', {'resultado': 'Teste\x00inválido'}).status_code, 400)
        with app.app_context():
            self.assertEqual(Movimentacao.query.count(), 0)
            self.assertIsNone(db.session.get(Protocolo, self.pid).finalizado_em)

    def test_deletion_keeps_number_reserved(self):
        from app import gerar_proximo_numero_protocolo
        from datetime import date
        from flask_login import login_user
        self.login('admin')
        self.post('excluir', {'confirmacao': '0001/2026', 'motivo': 'Teste de reserva de numeração'})
        with app.test_request_context('/'):
            login_user(db.session.get(Usuario, self.ids['admin']))
            db.session.get(Protocolo, self.pid).numero = f'9998/{date.today().year}'
            db.session.commit()
            self.assertEqual(gerar_proximo_numero_protocolo(), f'9999/{date.today().year}')

    def test_old_schema_upgrade_is_additive_and_idempotent(self):
        from bootstrap_db import bootstrap
        with app.app_context():
            db.session.remove()
            with db.engine.begin() as connection:
                for column in ('excluido_em', 'finalizado_em', 'resultado_final'):
                    connection.execute(text(f'ALTER TABLE protocolos DROP COLUMN {column}'))
                connection.execute(text('DROP TABLE movimentacoes'))
                connection.execute(text('CREATE TABLE movimentacoes (id INTEGER PRIMARY KEY, protocolo_id INTEGER NOT NULL, tenant_id INTEGER NOT NULL, setor_origem_id INTEGER, setor_destino_id INTEGER NOT NULL, destinatario_usuario_id INTEGER, enviado_por_id INTEGER NOT NULL, recebido_por_id INTEGER, enviado_em TIMESTAMP NOT NULL, recebido_em TIMESTAMP, observacao TEXT)'))
            bootstrap(); bootstrap()
            cols = {c['name'] for c in inspect(db.engine).get_columns('movimentacoes')}
            self.assertIn('providencia_id', cols)
            self.assertEqual(db.session.get(Protocolo, self.pid).numero, '0001/2026')
            self.assertEqual(db.session.get(Usuario, self.ids['admin']).senha, 'not-a-real-credential')


    def update_status(self, status, **extra):
        return self.client.post('/protocolos/atualizar', json={
            'protocoloId': self.pid, 'novoStatus': status, **extra})

    def test_receive_does_not_start_analysis_and_owner_can_update_during_workflow(self):
        self.login('admin'); self.send('alice')
        with app.app_context():
            self.assertEqual(db.session.get(Protocolo, self.pid).status, 'EM TRAMITAÇÃO')
        self.assertEqual(self.update_status('EM ANÁLISE').status_code, 409)
        self.receive('alice')
        with app.app_context():
            self.assertEqual(db.session.get(Protocolo, self.pid).status, 'RECEBIDO')
        html = self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True)
        self.assertIn('>Atualizar status</button>', html)
        self.assertEqual(self.update_status('EM ANÁLISE', observacao='Análise iniciada.').status_code, 200)
        self.assertEqual(self.update_status('PENDENTE DE DOCUMENTO', observacao='Falta certidão.').status_code, 200)
        with app.app_context():
            p = db.session.get(Protocolo, self.pid)
            self.assertEqual(p.status, 'PENDENTE DE DOCUMENTO')
            self.assertEqual(p.responsavel, 'alice')
            self.assertEqual(HistoricoProtocolo.query.filter_by(acao='ALTERACAO_STATUS').count(), 2)
            self.assertTrue(verify_audit_chain(self.tenant)[0])
        self.login('bob')
        self.assertEqual(self.update_status('EM ANÁLISE').status_code, 403)

    def test_parallel_receipts_and_completions_preserve_manual_work_status(self):
        self.login('admin'); self.send('alice', 'carol')
        self.receive('alice')
        self.assertEqual(self.update_status('PENDENTE DE DOCUMENTO').status_code, 200)
        self.receive('carol')
        with app.app_context():
            self.assertEqual(db.session.get(Protocolo, self.pid).status, 'PENDENTE DE DOCUMENTO')
        cid, _ = self.participation('carol')
        self.post(f'providencia/{cid}/concluir')
        with app.app_context():
            self.assertEqual(db.session.get(Protocolo, self.pid).status, 'PENDENTE DE DOCUMENTO')
        self.login('alice')
        aid, _ = self.participation('alice')
        self.send('bob', providencia_id=aid)
        with app.app_context():
            self.assertEqual(db.session.get(Protocolo, self.pid).status, 'EM TRAMITAÇÃO')
        self.assertEqual(self.update_status('EM ANÁLISE').status_code, 403)
        self.receive('bob')
        with app.app_context():
            self.assertEqual(db.session.get(Protocolo, self.pid).status, 'RECEBIDO')

    def test_manual_status_cannot_simulate_actions_or_change_custody(self):
        self.login('admin')
        for status in ('PROTOCOLO GERADO', 'AGUARDANDO RECEBIMENTO', 'RECEBIDO',
                       'EM TRAMITAÇÃO', 'CONCLUÍDO', 'FINALIZADO', 'ARQUIVADO'):
            self.assertEqual(self.update_status(status).status_code, 400)
        self.assertEqual(self.update_status('PENDENTE DE DOCUMENTO', novoResponsavel='bob').status_code, 409)
        self.assertEqual(self.update_status('PENDENTE DE DOCUMENTO', observacao=['invalid']).status_code, 400)
        self.update_status('PENDENTE DE DOCUMENTO')
        self.update_status('PENDENTE DE DOCUMENTO')
        with app.app_context():
            self.assertEqual(HistoricoProtocolo.query.filter_by(acao='ALTERACAO_STATUS').count(), 1)
            p = db.session.get(Protocolo, self.pid)
            p.status = 'CONCLUÍDO'; db.session.commit()
        self.assertEqual(self.update_status('EM ANÁLISE').status_code, 403)
        self.assertNotIn('>Atualizar status</button>', self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True))

    def test_document_request_survives_forward_and_blocks_false_analysis(self):
        self.login('admin'); self.send('alice', 'carol')
        with app.app_context():
            p = db.session.get(Protocolo, self.pid)
            p.status = 'PENDENTE DE DOCUMENTO'
            db.session.add(SolicitacaoComplemento(tenant_id=self.tenant, protocolo_id=self.pid,
                solicitado_por_id=self.ids['admin'], motivo='Envie a certidão faltante.', status='PENDENTE'))
            db.session.commit()
        self.receive('alice')
        self.assertEqual(self.update_status('EM ANÁLISE').status_code, 409)
        aid, _ = self.participation('alice')
        self.send('bob', providencia_id=aid)
        with app.app_context():
            self.assertEqual(db.session.get(Protocolo, self.pid).status, 'PENDENTE DE DOCUMENTO')
        self.receive('carol')
        with app.app_context():
            self.assertEqual(db.session.get(Protocolo, self.pid).status, 'PENDENTE DE DOCUMENTO')
        self.login('admin')
        self.assertEqual(self.post('finalizar').status_code, 409)

    def test_manual_document_pending_blocks_completion_and_archive(self):
        self.login('admin')
        self.assertEqual(self.update_status('PENDENTE DE DOCUMENTO').status_code, 200)
        self.assertEqual(self.post('finalizar').status_code, 409)
        self.post('arquivar')
        with app.app_context():
            self.assertIsNone(db.session.get(Protocolo, self.pid).arquivado_em)
        self.update_status('EM ANÁLISE')
        self.assertEqual(self.post('finalizar').status_code, 302)

    def test_completion_aliases_share_filters_display_and_dashboard(self):
        from datetime import date
        self.login('admin')
        with app.app_context():
            legacy = db.session.get(Protocolo, self.pid)
            legacy.status = 'FINALIZADO'
            legacy.data_solicitacao = date.today()
            canonical = Protocolo(tenant_id=self.tenant, numero='0002/2026',
                nome='Outro fictício', status='CONCLUÍDO', data_solicitacao=date.today())
            db.session.add(canonical); db.session.commit()
            self.assertEqual(legacy.status_exibicao, 'CONCLUÍDO')
        for value in ('FINALIZADO', 'CONCLUÍDO'):
            with self.subTest(status=value):
                html = self.client.get('/protocolos', query_string={'status': value}).get_data(as_text=True)
                self.assertIn('0001/2026', html)
                self.assertIn('0002/2026', html)
                self.assertNotIn('value="FINALIZADO"', html)
                stats = self.client.get('/protocolos/dashboard-stats', query_string={'status': value}).get_json()
                self.assertEqual(stats['statusProtocolos'], [{'status': 'CONCLUÍDO', 'total': 2}])
                self.assertEqual(stats['totalFinalizados'], 2)
        html = self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True)
        self.assertIn('Processo concluído', html)
        self.assertNotIn('href="#tramitacao"', html)
        self.assertEqual(self.post('finalizar').status_code, 302)
        with app.app_context():
            self.assertEqual(db.session.get(Protocolo, self.pid).status, 'FINALIZADO')
            self.assertEqual(HistoricoProtocolo.query.filter_by(acao='FINALIZACAO').count(), 0)


if __name__ == '__main__': unittest.main()
