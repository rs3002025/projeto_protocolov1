"""Formulário expirado: retorno compreensível e nova tentativa protegida."""
import re
from datetime import datetime
from unittest import TestCase
from unittest.mock import patch
import test_multitenancy as isolated
import test_protocol_workflow as fixture
from app import app, db
from models import Protocolo, HistoricoProtocolo
from wtforms.validators import ValidationError


class CsrfFeedbackTests(TestCase):
    setUp=fixture.WorkflowTests.setUp
    tearDown=fixture.WorkflowTests.tearDown
    login=fixture.WorkflowTests.login

    def test_expired_form_does_not_mutate_and_fresh_form_can_retry(self):
        self.login('admin')
        with app.app_context():
            p=db.session.get(Protocolo,self.pid)
            p.status='ARQUIVADO';p.arquivado_em=datetime.now();db.session.commit()
        app.config['WTF_CSRF_ENABLED']=True
        try:
            with patch('flask_wtf.csrf.validate_csrf',side_effect=ValidationError('The CSRF token has expired.')):
                response=self.client.post(f'/protocolo/{self.pid}/desarquivar',data={'justificativa':'Retomar análise.'})
            self.assertEqual(response.status_code,400)
            html=response.get_data(as_text=True)
            self.assertIn('Nenhuma alteração foi realizada.',html)
            self.assertIn('Voltar ao formulário',html)
            self.assertNotIn('The CSRF token has expired',html)
            self.assertIn(f'href="/protocolo/{self.pid}"',html)
            with app.app_context():
                self.assertEqual(db.session.get(Protocolo,self.pid).status,'ARQUIVADO')
                self.assertEqual(HistoricoProtocolo.query.count(),0)
            page=self.client.get(f'/protocolo/{self.pid}').get_data(as_text=True)
            token=re.search(r'name="csrf_token"[^>]*value="([^"]+)"',page).group(1)
            response=self.client.post(f'/protocolo/{self.pid}/desarquivar',data={'justificativa':'Retomar análise.','csrf_token':token})
            self.assertEqual(response.status_code,302)
            with app.app_context():
                self.assertEqual(db.session.get(Protocolo,self.pid).status,'EM ANÁLISE')
                self.assertEqual(HistoricoProtocolo.query.filter_by(acao='DESARQUIVAMENTO').count(),1)
        finally:
            app.config['WTF_CSRF_ENABLED']=False

    def test_login_csrf_failure_has_local_retry_without_echoing_password(self):
        app.config['WTF_CSRF_ENABLED']=True
        try:
            response=self.client.post('/login',data={'login':'ficticio','senha':'Nunca-Repetir-No-HTML'})
            self.assertEqual(response.status_code,400)
            html=response.get_data(as_text=True)
            self.assertIn('href="/login"',html)
            self.assertNotIn('Nunca-Repetir-No-HTML',html)
        finally:
            app.config['WTF_CSRF_ENABLED']=False
