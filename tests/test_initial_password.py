"""Primeiro acesso com contas fictícias e banco SQLite isolado."""
import re
from unittest import TestCase
from unittest.mock import patch

import test_multitenancy as isolated
import test_protocol_workflow as fixture
from sqlalchemy.exc import SQLAlchemyError
from app import app, bcrypt, db
from models import Usuario, Protocolo


class InitialPasswordTests(TestCase):
    setUp = fixture.WorkflowTests.setUp
    tearDown = fixture.WorkflowTests.tearDown

    temporary = 'Temporaria-QA-2026'
    personal = 'Pessoal-QA-2026'

    def csrf(self, client, path):
        html = client.get(path).get_data(as_text=True)
        return re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html).group(1)

    def create_account(self, role='tramitador'):
        creator = app.test_client()
        with creator.session_transaction() as state:
            state['_user_id'], state['_fresh'] = self.users['admin'], True
        response = creator.post('/admin/usuarios/novo', data={
            'nome_completo': 'Pessoa Fictícia', 'login': 'qa_' + role,
            'email': role + '@example.test', 'senha': self.temporary,
            'tipo': role, 'lotacao_id': self.sector, 'servidor_id': 0,
        })
        self.assertEqual(response.status_code, 302)
        with app.app_context():
            user = Usuario.query.filter_by(login='qa_' + role).one()
            self.assertTrue(user.deve_trocar_senha)
            return user.id, user.get_id()

    def sign_in(self, client, role='tramitador'):
        return client.post('/entrar/a?next=/protocolos', data={
            'login': 'qa_' + role, 'senha': self.temporary, 'remember': 'y',
        })

    def change(self, client, **overrides):
        data = {'senha_atual': self.temporary, 'senha_nova': self.personal,
                'confirmar_senha': self.personal}
        data.update(overrides)
        return client.post('/minha-conta/trocar-senha', data=data)

    def assert_pending(self, uid):
        with app.app_context():
            user = db.session.get(Usuario, uid)
            self.assertTrue(user.deve_trocar_senha)
            self.assertTrue(bcrypt.check_password_hash(user.senha, self.temporary))
            self.assertEqual(db.session.get(Protocolo, self.pid).status, 'EM ANÁLISE')

    def test_each_created_role_changes_password_without_permission_error(self):
        for role in ('tramitador', 'consulta', 'protocolista', 'admin'):
            with self.subTest(role=role):
                uid, _ = self.create_account(role)
                client = app.test_client()
                response = self.sign_in(client, role)
                self.assertEqual(response.location, '/minha-conta/trocar-senha')
                self.assertIsNone(client.get_cookie('remember_token'))
                response = self.change(client)
                destination = '/minha-conta/pin' if role in ('admin', 'protocolista') else '/home'
                self.assertEqual(response.location, destination)
                self.assertEqual(client.get(destination).status_code, 200)
                with app.app_context():
                    user = db.session.get(Usuario, uid)
                    self.assertFalse(user.deve_trocar_senha)
                    self.assertTrue(bcrypt.check_password_hash(user.senha, self.personal))
                    self.assertFalse(bcrypt.check_password_hash(user.senha, self.temporary))
                other = app.test_client()
                self.assertEqual(other.post('/entrar/a', data={
                    'login': 'qa_' + role, 'senha': self.temporary}).status_code, 200)
                self.assertEqual(other.get('/home').location, '/login')
                self.assertEqual(other.post('/entrar/a', data={
                    'login': 'qa_' + role, 'senha': self.personal}).status_code, 302)
                self.assertEqual(other.get('/home').status_code, 200)

    def test_failed_validation_never_unlocks_the_temporary_account(self):
        uid, _ = self.create_account()
        client = app.test_client()
        self.sign_in(client)
        for values in ({'senha_atual': 'Incorreta-QA'},
                       {'confirmar_senha': 'Diferente-QA'},
                       {'senha_nova': self.temporary, 'confirmar_senha': self.temporary},
                       {'senha_nova': 'curta', 'confirmar_senha': 'curta'}):
            with self.subTest(values=values):
                self.assertEqual(self.change(client, **values).status_code, 200)
                self.assert_pending(uid)
                for path in ('/', '/home', '/protocolos', '/meus-processos', '/pendencias-recebimento'):
                    self.assertEqual(client.get(path).location, '/minha-conta/trocar-senha')
                self.assertEqual(client.post(f'/protocolo/{self.pid}/status', data={
                    'status': 'CONCLUÍDO'}).location, '/minha-conta/trocar-senha')
        retry = app.test_client()
        self.assertEqual(self.sign_in(retry).location, '/minha-conta/trocar-senha')
        self.assertEqual(retry.get('/home').location, '/minha-conta/trocar-senha')

    def test_expired_form_preserves_the_requirement_and_allows_protected_retry(self):
        uid, _ = self.create_account()
        client = app.test_client()
        self.sign_in(client)
        app.config['WTF_CSRF_ENABLED'] = True
        try:
            response = self.change(client)
            self.assertEqual(response.status_code, 400)
            self.assertIn('href="/minha-conta/trocar-senha"', response.get_data(as_text=True))
            self.assert_pending(uid)
            self.assertEqual(client.get('/home').location, '/minha-conta/trocar-senha')
            token = self.csrf(client, '/minha-conta/trocar-senha')
            self.assertEqual(self.change(client, csrf_token=token).location, '/home')
        finally:
            app.config['WTF_CSRF_ENABLED'] = False

    def test_database_failure_preserves_password_and_restriction_until_retry(self):
        uid, _ = self.create_account()
        client = app.test_client()
        self.sign_in(client)
        with self.assertLogs(app.logger, level='ERROR') as logs:
            with patch.object(db.session, 'commit', side_effect=SQLAlchemyError('Falha fictícia')):
                response = self.change(client)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('Falha fictícia', response.get_data(as_text=True))
        self.assertIn('SQLAlchemyError', ' '.join(logs.output))
        self.assertNotIn(self.temporary, ' '.join(logs.output))
        self.assertNotIn(self.personal, ' '.join(logs.output))
        self.assert_pending(uid)
        self.assertEqual(client.get('/home').location, '/minha-conta/trocar-senha')
        self.assertEqual(self.change(client).location, '/home')

    def test_success_invalidates_other_sessions_using_the_temporary_credential(self):
        self.create_account()
        first, second = app.test_client(), app.test_client()
        self.sign_in(first)
        self.sign_in(second)
        self.assertEqual(self.change(first).location, '/home')
        self.assertEqual(second.get('/home').location, '/login')
        self.assertEqual(first.get('/home').status_code, 200)

    def test_oversized_new_password_returns_validation_instead_of_bcrypt_error(self):
        uid, _ = self.create_account()
        client = app.test_client()
        self.sign_in(client)
        for candidate in ('a' * 73, 'á' * 37):
            with self.subTest(candidate_length=len(candidate)):
                response = self.change(client, senha_nova=candidate, confirmar_senha=candidate)
                self.assertEqual(response.status_code, 200)
                self.assertIn('senha mais curta', response.get_data(as_text=True))
                self.assert_pending(uid)

    def test_platform_first_login_also_has_no_persistent_temporary_session(self):
        with app.app_context():
            user = Usuario(tenant_id=None, is_platform_admin=True, nome='QA Plataforma',
                           login='qa_plataforma', tipo='admin', deve_trocar_senha=True,
                           senha=bcrypt.generate_password_hash(self.temporary).decode())
            db.session.add(user)
            db.session.commit()
            uid = user.id
        client = app.test_client()
        response = client.post('/login?next=/protocolos', data={
            'login': 'qa_plataforma', 'senha': self.temporary, 'remember': 'y'})
        self.assertEqual(response.location, '/minha-conta/trocar-senha')
        self.assertIsNone(client.get_cookie('remember_token'))
        self.assertEqual(self.change(client).location, '/minha-conta/pin')
        self.assertEqual(client.get('/minha-conta/pin').status_code, 200)
        with app.app_context():
            self.assertFalse(db.session.get(Usuario, uid).deve_trocar_senha)

    def test_remember_stays_available_after_the_initial_change_has_been_completed(self):
        uid, _ = self.create_account()
        with app.app_context():
            db.session.get(Usuario, uid).deve_trocar_senha = False
            db.session.commit()
        client = app.test_client()
        self.assertEqual(self.sign_in(client).location, '/protocolos')
        self.assertIsNotNone(client.get_cookie('remember_token'))
        self.assertEqual(client.get('/home').status_code, 200)
