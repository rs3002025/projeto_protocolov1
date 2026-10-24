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

    def test_single_flow_stays_simple_and_admin_can_close_without_extra_step(self):
        self.login('admin'); self.send('alice')
        self.assertEqual(self.post('finalizar').status_code, 409)
        self.receive('alice')
        html = self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True)
        self.assertIn('data-forward-protocol', html)
        self.assertIn('>Encaminhar protocolo</button>', html)
        self.assertIn('>Atualizar status</button>', html)
        self.assertNotIn('Encaminhar esta participação', html)
        self.assertNotIn('Providência 1', html)
        self.assertNotIn('Gerar nova versão do requerimento', html)
        self.assertIn(self.post('finalizar').status_code, (302, 403))
        with app.app_context():
            self.assertNotEqual(db.session.get(Protocolo, self.pid).status, 'CONCLUÍDO')
        self.login('admin')
        self.assertEqual(self.post('finalizar', {'resultado': 'Deferido.'}).status_code, 302)
        with app.app_context():
            p = db.session.get(Protocolo, self.pid)
            self.assertEqual(p.status, 'CONCLUÍDO')
            self.assertIsNotNone(p.providencias[0].concluida_em)
            self.assertEqual(p.providencias[0].concluida_por_id, self.ids['admin'])
            self.assertTrue(verify_audit_chain(self.tenant)[0])

    def test_edit_pdf_failure_rolls_back_data_and_preserves_previous_document(self):
        from unittest.mock import patch
        self.login('admin')
        with patch('app.render_protocol_pdf', return_value=b'%PDF-1.7 fictitious old document'):
            self.assertEqual(self.client.post(f'/protocolo/{self.pid}/documento/gerar').status_code, 200)
        with app.app_context():
            p = db.session.get(Protocolo, self.pid)
            original = p.nome
        with patch('app.render_protocol_pdf', side_effect=RuntimeError('Fictitious renderer failure')):
            self.assertEqual(self.client.post(f'/protocolo/{self.pid}/editar', data={'nome': 'Nome corrigido fictício'}).status_code, 302)
        with app.app_context():
            self.assertEqual(db.session.get(Protocolo, self.pid).nome, original)
            self.assertEqual(Anexo.query.filter_by(protocolo_id=self.pid, documento_chave='documento-protocolo').count(), 1)
            self.assertEqual(HistoricoProtocolo.query.filter_by(acao='EDICAO').count(), 0)
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
        self.assertEqual(self.post(f'providencia/{bob}/concluir').status_code, 409)
        html = self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True)
        self.assertIn('data-forward-protocol', html)
        self.assertNotIn('Concluir minha participação', html)
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
        self.login('bob'); self.assertEqual(self.send('carol', providencia_id=aid).status_code, 409)

    def test_watching_is_per_user_idempotent_and_survives_transfer(self):
        self.login('protocolista')
        for _ in range(2): self.assertEqual(self.post('acompanhar', {'acompanhar': '1'}).status_code, 302)
        self.send('alice'); self.receive('alice')
        html = self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True)
        self.assertIn('data-forward-protocol', html)
        self.assertNotIn('Concluir minha participação', html)
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
        for label in ('Acompanhar processo', 'Concluir processo', 'Excluir protocolo', 'Participação 1', 'Participação 2', 'Receber participação'):
            self.assertIn(label, html)
        self.assertIn('data-forward-protocol', html)
        self.assertIn('+ Adicionar encaminhamento', html)
        self.assertIn('data-additional-forward', html)
        self.assertIn('data-destination-title>Destino 2</legend>', html)
        self.assertNotIn('id="destinatarios-multiplos"', html)
        self.assertIn('Encaminhamento a transferir', html)
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

    def test_managers_can_intervene_after_send_without_faking_receipts(self):
        self.login('admin'); self.send('alice')
        original, original_movement = self.participation('alice')
        for manager, recipient in [('admin', 'carol'), ('protocolista', 'bob')]:
            self.login(manager)
            html = self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True)
            self.assertIn('data-forward-protocol', html)
            self.assertNotIn('name="nova_providencia"', html)
            self.assertEqual(self.send(recipient, nova_providencia='1').status_code, 302)
        with app.app_context():
            self.assertEqual(ProvidenciaProtocolo.query.count(), 1)
            self.assertEqual(Movimentacao.query.count(), 3)
            self.assertIsNone(db.session.get(Movimentacao, original_movement).recebido_em)
            self.assertIsNone(db.session.get(ProvidenciaProtocolo, original).concluida_em)
            events = HistoricoProtocolo.query.filter_by(acao='TRAMITACAO').order_by(HistoricoProtocolo.id).all()
            self.assertEqual(len(events), 3)
            self.assertEqual([h.usuario_id for h in events[-2:]], [self.ids['admin'], self.ids['protocolista']])
            self.assertTrue(all('Transferência administrativa' not in h.observacao for h in events))
            from protocol_workflow import pending_movement_condition
            self.assertEqual(Movimentacao.query.filter(pending_movement_condition()).count(), 1)
            self.assertTrue(verify_audit_chain(self.tenant)[0])
        self.login('alice')
        self.assertEqual(self.post('receber', {'movimentacao_id': original_movement}).status_code, 409)
        self.assertEqual(self.send('carol', nova_providencia='1').status_code, 409)
        self.assertNotIn('data-forward-protocol', self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True))
        self.receive('bob')
        self.login('admin')
        self.assertEqual(self.post('finalizar').status_code, 302)
        self.assertEqual(self.post('arquivar').status_code, 302)
        with app.app_context(): self.assertIsNotNone(db.session.get(Protocolo, self.pid).arquivado_em)

    def test_manual_sector_route_without_external_users_has_one_current_destination(self):
        self.login('protocolista')
        with app.app_context():
            sectors = [Lotacao(tenant_id=self.tenant, nome=n) for n in ('SEDUC sem usuário', 'SESA sem usuário')]
            db.session.add_all(sectors); db.session.commit()
            sector_ids = [s.id for s in sectors]
        for sector in sector_ids:
            self.assertEqual(self.post('tramitar', {'setor_destino_id': sector,
                'observacao': 'Resposta recebida fora do sistema; seguir ao próximo setor.'}).status_code, 302)
        self.assertEqual(self.post('tramitar', {'setor_destino_id': self.sector,
            'destinatario_usuario_id': self.ids['protocolista']}).status_code, 302)
        with app.app_context():
            from protocol_workflow import pending_movement_condition
            self.assertEqual(ProvidenciaProtocolo.query.count(), 1)
            self.assertEqual(Movimentacao.query.count(), 3)
            self.assertEqual(Movimentacao.query.filter(pending_movement_condition()).count(), 1)
            self.assertEqual(Movimentacao.query.filter(Movimentacao.recebido_em.is_not(None)).count(), 0)
        self.assertEqual(self.post('receber').status_code, 302)
        with app.app_context():
            self.assertEqual(db.session.get(Protocolo, self.pid).responsavel, 'protocolista')
            self.assertEqual(Movimentacao.query.filter(pending_movement_condition()).count(), 0)
            self.assertTrue(verify_audit_chain(self.tenant)[0])

    def test_manager_transfers_already_received_branch_without_adding_owner(self):
        self.login('admin'); self.send('alice')
        self.receive('alice')
        aid, received_id = self.participation('alice')
        self.login('protocolista')
        self.assertEqual(self.send('carol', providencia_id=aid, observacao='Resposta do setor entregue à equipe.').status_code, 302)
        with app.app_context():
            from protocol_workflow import can_work
            self.assertEqual(ProvidenciaProtocolo.query.count(), 1)
            self.assertEqual(db.session.get(Movimentacao, received_id).recebido_por_id, self.ids['alice'])
            self.assertEqual(db.session.get(ProvidenciaProtocolo, aid).movimento_atual.destinatario_usuario_id, self.ids['carol'])
        self.login('alice')
        self.assertEqual(self.send('bob', providencia_id=aid).status_code, 403)

    def test_legacy_pending_movement_is_preserved_but_not_left_open(self):
        self.login('admin')
        with app.app_context():
            old = Movimentacao(tenant_id=self.tenant, protocolo_id=self.pid, setor_destino_id=self.sector,
                enviado_por_id=self.ids['admin'], destinatario_usuario_id=self.ids['alice'])
            db.session.add(old); db.session.commit(); old_id = old.id
        self.assertEqual(self.send('carol').status_code, 302)
        with app.app_context():
            from protocol_workflow import pending_movement_condition
            self.assertEqual(ProvidenciaProtocolo.query.count(), 1)
            old = db.session.get(Movimentacao, old_id)
            self.assertIsNotNone(old.providencia_id)
            self.assertIsNone(old.recebido_em)
            self.assertEqual(Movimentacao.query.filter(pending_movement_condition()).count(), 1)
            self.assertNotEqual(Movimentacao.query.filter(pending_movement_condition()).one().id, old_id)

    def test_manager_must_select_one_parallel_branch_to_transfer(self):
        self.login('admin'); self.send('alice', 'bob')
        aid, old_id = self.participation('alice')
        bid, bob_movement = self.participation('bob')
        self.assertEqual(self.send('carol', nova_providencia='1').status_code, 409)
        self.assertEqual(self.send('foreign', providencia_id=aid).status_code, 404)
        self.assertEqual(self.send('carol', providencia_id=aid).status_code, 302)
        with app.app_context():
            self.assertEqual(ProvidenciaProtocolo.query.count(), 2)
            self.assertEqual(db.session.get(ProvidenciaProtocolo, bid).movimento_atual.id, bob_movement)
            self.assertNotEqual(db.session.get(ProvidenciaProtocolo, aid).movimento_atual.id, old_id)
            self.assertIsNone(db.session.get(Movimentacao, old_id).recebido_em)

    def test_explicit_parallel_tool_preserves_legacy_destination_too(self):
        self.login('admin')
        with app.app_context():
            old = Movimentacao(tenant_id=self.tenant, protocolo_id=self.pid, setor_destino_id=self.sector,
                enviado_por_id=self.ids['admin'], destinatario_usuario_id=self.ids['alice'])
            db.session.add(old); db.session.commit(); old_id = old.id
        self.assertEqual(self.send('bob', envio_coletivo='1').status_code, 302)
        with app.app_context():
            from protocol_workflow import pending_movement_condition
            self.assertEqual(ProvidenciaProtocolo.query.count(), 2)
            self.assertEqual(db.session.get(Movimentacao, old_id).providencia.movimento_atual.id, old_id)
            self.assertEqual(Movimentacao.query.filter(pending_movement_condition()).count(), 2)

    def test_additional_fields_keep_existing_destination_and_individual_notes(self):
        self.login('admin'); self.send('alice')
        aid, original = self.participation('alice')
        with app.app_context(): other_sector = db.session.get(Usuario, self.ids['carol']).lotacao_id
        data = {'envio_coletivo':'1', 'destinos_formato':'campos',
            'destinos_setores':[str(self.sector), str(other_sector)],
            'destinos_usuarios':['', str(self.ids['carol'])],
            'destinos_observacoes':['Resposta para o setor.\nOutra linha.', 'Parecer individual.'],
            'envio_token':'additional-fields-isolated-token'}
        for _ in range(2): self.assertEqual(self.post('tramitar', data).status_code, 302)
        with app.app_context():
            moves = Movimentacao.query.order_by(Movimentacao.id).all()
            self.assertEqual(len(moves), 3)
            self.assertEqual(ProvidenciaProtocolo.query.count(), 3)
            self.assertEqual(db.session.get(ProvidenciaProtocolo, aid).movimento_atual.id, original)
            self.assertIsNone(moves[1].destinatario_usuario_id)
            self.assertEqual(moves[2].destinatario_usuario_id, self.ids['carol'])
            self.assertEqual([m.observacao for m in moves[1:]], data['destinos_observacoes'])
            self.assertTrue(verify_audit_chain(self.tenant)[0])

    def test_additional_fields_validate_all_destinations_before_writing(self):
        self.login('admin'); self.send('alice')
        with app.app_context():
            foreign = Lotacao(tenant_id=self.foreign_tenant, nome='Setor de outro cliente')
            db.session.add(foreign); db.session.commit(); foreign_id = foreign.id
        base = {'envio_coletivo':'1', 'destinos_formato':'campos',
            'destinos_setores':[str(self.sector)], 'destinos_usuarios':[''], 'destinos_observacoes':['Nota']}
        cases = [
            ({'destinos_setores':[str(self.sector), str(foreign_id)], 'destinos_usuarios':['',''], 'destinos_observacoes':['A','B']},404),
            ({'destinos_usuarios':[str(self.ids['carol'])]},404),
            ({'destinos_setores':[str(self.sector), '0'+str(self.sector)], 'destinos_usuarios':['',''], 'destinos_observacoes':['A','B']},400),
            ({'destinos_usuarios':[]},400),
            ({'destinos_observacoes':['x\x00y']},400),
            ({'destinos_observacoes':['x'*10001]},400),
            ({'envio_coletivo':'0'},400),
            ({'destinatarios_ids':[str(self.ids['bob'])]},400),
            ({'destinos_setores':[str(self.sector)]*51, 'destinos_usuarios':['']*51, 'destinos_observacoes':['']*51},400),
        ]
        for override, status in cases:
            with self.subTest(override=list(override)):
                self.assertEqual(self.post('tramitar', {**base, **override}).status_code, status)
                with app.app_context():
                    self.assertEqual(Movimentacao.query.count(), 1)
                    self.assertEqual(ProvidenciaProtocolo.query.count(), 1)

    def test_additional_fields_do_not_expand_worker_permissions(self):
        self.login('admin'); self.send('alice'); self.receive('alice')
        data = {'envio_coletivo':'1', 'destinos_formato':'campos', 'destinos_setores':[str(self.sector)],
            'destinos_usuarios':[str(self.ids['bob'])], 'destinos_observacoes':['Solicito parecer.']}
        self.assertEqual(self.post('tramitar', data).status_code, 302)
        self.assertEqual(self.post('tramitar', data).status_code, 409)
        self.login('consulta')
        self.assertIn(self.post('tramitar', data).status_code, (302,403))
        self.login('admin')
        self.assertEqual(self.client.post(f'/protocolo/{self.foreign_pid}/tramitar', data=data).status_code, 404)
        with app.app_context(): self.assertEqual(ProvidenciaProtocolo.query.count(), 2)

    def test_only_explicit_parallel_tool_adds_another_active_responsibility(self):
        self.login('admin'); self.send('alice')
        aid, old_id = self.participation('alice')
        token = 'parallel-explicit-fictitious-token'
        for _ in range(2):
            self.assertEqual(self.send('bob', envio_coletivo='1', envio_token=token).status_code, 302)
        with app.app_context():
            self.assertEqual(ProvidenciaProtocolo.query.count(), 2)
            self.assertEqual(Movimentacao.query.count(), 2)
            self.assertEqual(db.session.get(ProvidenciaProtocolo, aid).movimento_atual.id, old_id)
        self.receive('alice')
        self.assertEqual(self.send('carol', envio_coletivo='1').status_code, 409)

    def test_managers_cannot_bypass_closed_process(self):
        self.login('admin'); self.send('alice')
        with app.app_context():
            p = db.session.get(Protocolo, self.pid)
            p.status = 'CONCLUÍDO'; db.session.commit()
        for manager in ('admin', 'protocolista'):
            self.login(manager)
            self.assertEqual(self.send('carol', nova_providencia='1').status_code, 409)
            self.assertNotIn('data-forward-protocol', self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True))

    def test_collective_blocks_forward_until_only_one_active_holder_remains(self):
        self.login('protocolista'); self.send('alice', 'bob')
        self.receive('alice'); aid, _ = self.participation('alice')
        self.receive('bob')
        self.login('alice')
        html = self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True)
        self.assertIn('Concluir minha participação', html)
        self.assertNotIn('data-forward-protocol', html)
        self.assertEqual(self.send('carol', providencia_id=aid).status_code, 409)
        with app.app_context(): self.assertEqual(Movimentacao.query.count(), 2)
        self.login('bob'); bid, _ = self.participation('bob')
        self.assertEqual(self.post(f'providencia/{bid}/concluir').status_code, 302)
        self.login('alice')
        html = self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True)
        self.assertIn('data-forward-protocol', html)
        self.assertNotIn('Concluir minha participação', html)
        self.assertEqual(self.post(f'providencia/{aid}/concluir').status_code, 409)
        self.assertEqual(self.send('carol', providencia_id=aid).status_code, 302)
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
        self.assertEqual(self.send('bob', providencia_id=aid).status_code, 302)
        with app.app_context():
            self.assertEqual(db.session.get(Protocolo, self.pid).status, 'EM TRAMITAÇÃO')
        self.assertEqual(self.update_status('EM ANÁLISE').status_code, 403)
        self.receive('bob')
        with app.app_context():
            self.assertEqual(db.session.get(Protocolo, self.pid).status, 'RECEBIDO')

    def test_manual_status_cannot_simulate_actions_or_change_custody(self):
        self.login('admin')
        for status in ('PROTOCOLO GERADO', 'AGUARDANDO RECEBIMENTO', 'RECEBIDO',
                       'EM TRAMITAÇÃO', 'AGUARDANDO CONCLUSÃO', 'CONCLUÍDO', 'FINALIZADO', 'ARQUIVADO'):
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
        self.receive('carol')
        cid, _ = self.participation('carol')
        self.assertEqual(self.post(f'providencia/{cid}/concluir').status_code, 302)
        self.login('alice')
        self.assertEqual(self.send('bob', providencia_id=aid).status_code, 302)
        with app.app_context():
            self.assertEqual(db.session.get(Protocolo, self.pid).status, 'PENDENTE DE DOCUMENTO')
        self.receive('bob')
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
