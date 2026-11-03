"""Login incorreto e limitação de tentativas com contas locais fictícias."""
from unittest import TestCase
import test_multitenancy as isolated
import test_protocol_workflow as fixture
from app import app, db, bcrypt
from models import Usuario


class LoginFeedbackTests(TestCase):
    setUp = fixture.WorkflowTests.setUp
    tearDown = fixture.WorkflowTests.tearDown

    def test_ajax_login_returns_destination_without_loading_home_and_native_keeps_redirect(self):
        for global_account in (False, True):
            with self.subTest(global_account=global_account):
                path = self.account(global_account)
                client = app.test_client()
                response = client.post(path, data={'login':'qa_login','senha':'Ficticio-Teste-2026'},
                                       headers={'X-Login-Request':'1','Accept':'application/json'},
                                       follow_redirects=True)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.history, ())
                self.assertTrue(response.is_json)
                self.assertEqual(response.json['redirect_to'], '/plataforma' if global_account else '/home')
                self.assertIn('no-store', response.headers['Cache-Control'])
                with client.session_transaction() as login_session:
                    self.assertIn('_user_id', login_session)
                native = app.test_client().post(path, data={'login':'qa_login','senha':'Ficticio-Teste-2026'})
                self.assertEqual(native.status_code, 302)

    def test_ajax_wrong_password_does_not_create_session(self):
        path = self.account()
        client = app.test_client()
        response = client.post(path, data={'login':'qa_login','senha':'Incorreta-Ficticia'},
                               headers={'X-Login-Request':'1','Accept':'application/json'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('Não foi possível autenticar.', response.get_data(as_text=True))
        self.assertEqual(client.get('/protocolos').status_code, 302)

    def account(self, global_account=False):
        with app.app_context():
            user = Usuario(tenant_id=None if global_account else self.tenant,
                           is_platform_admin=global_account, nome='QA Login', login='qa_login',
                           tipo='admin', senha=bcrypt.generate_password_hash('Ficticio-Teste-2026').decode())
            db.session.add(user); db.session.commit()
        return '/login' if global_account else '/entrar/a'

    def test_wrong_password_has_visible_error_and_correct_password_can_retry(self):
        for global_account in (False, True):
            with self.subTest(global_account=global_account):
                path = self.account(global_account)
                client = app.test_client()
                response = client.post(path, data={'login':'qa_login','senha':'Incorreta-Ficticia'})
                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)
                self.assertIn('Não foi possível autenticar. Verifique os dados informados.', html)
                self.assertIn('data-login-feedback', html)
                self.assertNotIn('Incorreta-Ficticia', html)
                self.assertEqual(client.get('/protocolos').status_code, 302)
                self.assertEqual(client.post(path, data={'login':'qa_login','senha':'Ficticio-Teste-2026'}).status_code, 302)

    def test_repeated_wrong_password_is_limited_without_silently_authenticating(self):
        path = self.account(True)
        client = app.test_client()
        for _ in range(5):
            self.assertEqual(client.post(path, data={'login':'qa_login','senha':'Incorreta-Ficticia'}).status_code, 200)
        response = client.post(path, data={'login':'qa_login','senha':'Incorreta-Ficticia'})
        self.assertEqual(response.status_code, 429)
        self.assertIn('Aguarde alguns minutos', response.get_data(as_text=True))
        self.assertEqual(client.get('/protocolos').status_code, 302)
