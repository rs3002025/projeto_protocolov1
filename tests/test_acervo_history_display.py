"""Acervo importado: apresentação útil, eventos originais intactos."""
from datetime import datetime
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import pytest

import test_multitenancy as base
import test_process_export as export_fixture
from app import app, db, history_parts, history_visible, history_actor_label
from models import HistoricoProtocolo, Protocolo


@pytest.fixture(scope='session', autouse=True)
def close_isolated_database_after_tests():
    yield
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


class AcervoHistoryTests(TestCase):
    setUp = export_fixture.ProcessExportTests.setUp
    tearDown = export_fixture.ProcessExportTests.tearDown
    login = export_fixture.ProcessExportTests.login
    attachment = export_fixture.ProcessExportTests.attachment
    section = export_fixture.ProcessExportTests.section

    def test_screenshot_messages_are_clean_and_audit_is_not_rewritten(self):
        cases = [
            ('ATUALIZACAO', 'Autoria do cadastro atribuída a Emily Gomes de Souza conforme acervo.', False, '', ''),
            ('ALTERACAO_STATUS', 'Em tramitação: sem conclusão definida no acervo de 2026.', False, '', ''),
            ('TRAMITACAO', 'Encaminhado para Planejamento e gestão (SEPLAG) — Claudeci Moreira de Sousa.\n\nConforme relatório de expedientes.', True, 'Encaminhado para Planejamento e gestão (SEPLAG) — Claudeci Moreira de Sousa.', ''),
            ('RECEBIMENTO', 'Recebimento registrado em nome de Claudeci Moreira de Sousa, conforme regularização do acervo.', True, 'Recebido por Claudeci Moreira de Sousa.', ''),
        ]
        for action, note, visible, system, observation in cases:
            event = SimpleNamespace(acao=action, observacao=note, responsavel='Regularização do acervo')
            self.assertEqual(bool(history_visible(event)), visible)
            self.assertEqual(history_actor_label(event), '')
            if visible:
                self.assertEqual(history_parts(event), {'sistema':system, 'observacao':observation})
            self.assertEqual(event.observacao, note)

    def test_real_user_text_and_real_actor_are_preserved(self):
        note = 'Em tramitação: sem conclusão definida no acervo de 2026.'
        event = SimpleNamespace(acao='ALTERACAO_STATUS', observacao=note, responsavel='emily', usuario_id=6)
        self.assertTrue(history_visible(event))
        self.assertEqual(history_parts(event)['observacao'], note)
        self.assertEqual(history_actor_label(event, {6:'Emily'}), 'Emily')
        event = SimpleNamespace(acao='TRAMITACAO', observacao='Encaminhado para SEPLAG.\n\nParecer recebido.\nAguardar documento.', responsavel='Regularização do acervo')
        self.assertEqual(history_parts(event)['observacao'], 'Parecer recebido.\nAguardar documento.')
        event = SimpleNamespace(acao='RECEBIMENTO', observacao='Documento recebido com ressalva.', responsavel='Regularização do acervo')
        self.assertEqual(history_parts(event)['observacao'], event.observacao)

    def test_internal_page_and_download_use_the_same_clean_history(self):
        self.login('admin'); self.attachment()
        notes = [
            ('ATUALIZACAO','Autoria do cadastro atribuída a Emily Gomes de Souza conforme acervo.'),
            ('ALTERACAO_STATUS','Em tramitação: sem conclusão definida no acervo de 2026.'),
            ('TRAMITACAO','Encaminhado para Planejamento e gestão (SEPLAG) — Claudeci Moreira de Sousa.\n\nConforme relatório de expedientes.'),
            ('RECEBIMENTO','Recebimento registrado em nome de Claudeci Moreira de Sousa, conforme regularização do acervo.'),
        ]
        with app.app_context():
            db.session.get(Protocolo,self.pid).modalidade_abertura='legado_importado'
            for i,(action,note) in enumerate(notes):
                db.session.add(HistoricoProtocolo(tenant_id=self.tenant, protocolo_id=self.pid,
                    acao=action, observacao=note, responsavel='Regularização do acervo',
                    status='EM TRAMITAÇÃO', data_movimentacao=datetime(2026,10,23,12,i)))
            db.session.commit()
            before=[(h.id,h.observacao,h.responsavel) for h in HistoricoProtocolo.query.filter_by(protocolo_id=self.pid).all()]
        html=self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True)
        self.assertIn('Recebido por Claudeci Moreira de Sousa.',html)
        for unwanted in ('Regularização do acervo','sem conclusão definida no acervo','Conforme relatório de expedientes','conforme regularização'):
            self.assertNotIn(unwanted,html)
        with patch('protocol_export.render_section',side_effect=self.section) as render:
            response=self.client.get(f'/protocolo/{self.pid}/processo/baixar?formato=pdf')
            self.assertEqual(response.status_code,200)
            timeline=next(c.kwargs['timeline'] for c in render.call_args_list if c.kwargs.get('section')=='history')
            self.assertEqual([e['title'] for e in timeline],['Encaminhamento','Recebimento'])
            self.assertTrue(all(not e['actor'] and not e['note'] for e in timeline))
        with app.app_context():
            self.assertEqual(before,[(h.id,h.observacao,h.responsavel) for h in HistoricoProtocolo.query.filter_by(protocolo_id=self.pid).all()])
