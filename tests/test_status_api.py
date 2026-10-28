"""Contrato real do modal: IDs de inputs HTML, erros e isolamento entre clientes."""
from unittest import TestCase
from sqlalchemy import event
import test_multitenancy as isolated
import test_protocol_workflow as fixture
from app import app, db
from models import Protocolo, HistoricoProtocolo


class StatusApiTests(TestCase):
    setUp = fixture.WorkflowTests.setUp
    tearDown = fixture.WorkflowTests.tearDown
    login = fixture.WorkflowTests.login

    def update(self, identifier, **extra):
        return self.client.post('/protocolos/atualizar', json={
            'protocoloId': identifier, 'novoStatus': 'PENDENTE DE DOCUMENTO', **extra})

    def test_html_string_id_is_bound_as_integer_and_persisted_once(self):
        self.login('admin')
        bindings = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            if 'FOR UPDATE' in statement or ('SELECT protocolos.id' in statement and 'protocolos.id =' in statement):
                bindings.append(context.compiled_parameters)
        with app.app_context():
            engine = db.engine
        event.listen(engine, 'before_cursor_execute', capture)
        try:
            response = self.update(str(self.pid), observacao='Aguardar certidão.')
        finally:
            event.remove(engine, 'before_cursor_execute', capture)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['sucesso'])
        self.assertTrue(any(type(params[0].get('id_1')) is int for params in bindings if params))
        self.assertEqual(self.update(self.pid).status_code, 200)
        with app.app_context():
            self.assertEqual(db.session.get(Protocolo, self.pid).status, 'PENDENTE DE DOCUMENTO')
            self.assertEqual(HistoricoProtocolo.query.filter_by(acao='ALTERACAO_STATUS').count(), 1)

    def test_invalid_ids_and_payloads_do_not_mutate(self):
        self.login('admin')
        for identifier in (None, True, False, 0, -1, 1.5, '', '1.0', '1 OR 1=1', [], {}, '9'*100, 2147483648):
            with self.subTest(identifier=identifier):
                r = self.update(identifier)
                self.assertEqual(r.status_code, 400)
                self.assertFalse(r.json['sucesso'])
        for value in (None, True, [], {}):
            self.assertEqual(self.update(self.pid, novoStatus=value).status_code, 400)
        with app.app_context():
            self.assertEqual(db.session.get(Protocolo, self.pid).status, 'EM ANÁLISE')
            self.assertEqual(HistoricoProtocolo.query.count(), 0)

    def test_foreign_missing_forbidden_and_expired_session_are_json(self):
        self.login('admin')
        for identifier in (self.foreign_pid, 2147483647):
            r = self.update(str(identifier))
            self.assertEqual(r.status_code, 404)
            self.assertFalse(r.json['sucesso'])
        self.login('consulta')
        self.assertEqual(self.update(self.pid).status_code, 403)
        with self.client.session_transaction() as session:
            session.clear()
        r = self.update(self.pid)
        self.assertEqual(r.status_code, 401)
        self.assertIn('sessão expirou', r.json['mensagem'])
        self.assertEqual(self.client.get('/protocolos').status_code, 302)

    def test_csrf_rejection_is_json_without_disabling_protection(self):
        self.login('admin')
        app.config['WTF_CSRF_ENABLED'] = True
        try:
            r = self.update(self.pid)
            self.assertEqual(r.status_code, 400)
            self.assertIn('segurança', r.json['mensagem'])
            self.assertEqual(self.client.post('/login').status_code, 400)
        finally:
            app.config['WTF_CSRF_ENABLED'] = False
