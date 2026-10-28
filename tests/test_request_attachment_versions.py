"""Novos requerimentos listam só as versões atuais dos anexos do envio."""
from unittest import TestCase
from flask import render_template
import test_multitenancy as isolated
import test_process_export as fixture
from app import app, db
from models import Protocolo, Organizacao


class RequestAttachmentVersionsTests(TestCase):
    setUp=fixture.ProcessExportTests.setUp
    tearDown=fixture.ProcessExportTests.tearDown
    attachment=fixture.ProcessExportTests.attachment

    def test_replaced_and_generated_documents_are_not_listed_as_current_attachments(self):
        self.attachment('versao-antiga.txt','documento-a',b'old',version=1,mime='text/plain')
        self.attachment('versao-atual.txt','documento-a',b'new',version=2,mime='text/plain')
        self.attachment('pedido-gerado.pdf','documento-protocolo')
        self.attachment('pedido-assinado.pdf','protocolo-autenticado')
        self.attachment('independente.txt','documento-b',b'independent',mime='text/plain')
        with app.app_context(),app.test_request_context('/'):
            html=render_template('pdf_template.html',protocolo=db.session.get(Protocolo,self.pid),
                organizacao=db.session.get(Organizacao,self.tenant),emissao=None,
                qr_code_url=None,qr_validacao_url=None,pdf_logo_url=None)
        self.assertIn('versao-atual.txt',html)
        self.assertIn('independente.txt',html)
        for name in ('versao-antiga.txt','pedido-gerado.pdf','pedido-assinado.pdf'):
            self.assertNotIn(name,html)
