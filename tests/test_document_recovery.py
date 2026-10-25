"""Recuperação permite exclusivamente os bytes originais comprovados."""
import hashlib,io
from unittest import TestCase
import test_multitenancy as _isolated_database_setup
import test_protocol_workflow as fixture
from app import app,db,read_attachment_bytes,verify_audit_chain
from models import Anexo,EmissaoEletronica


class DocumentRecoveryTests(TestCase):
    setUp=fixture.WorkflowTests.setUp
    tearDown=fixture.WorkflowTests.tearDown
    login=fixture.WorkflowTests.login

    def create_file(self,tenant=None):
        self.original=b'%PDF-1.7\noriginal-ficticio-preservado'
        with app.app_context():
            item=Anexo(tenant_id=tenant or self.tenant,protocolo_id=self.foreign_pid if tenant else self.pid,
                documento_chave='documento-protocolo',versao=8,file_name='original.pdf',storage_path='fonte-preservada',
                storage_backend='database',file_data=None,file_size=len(self.original),mime_type='application/pdf',
                file_hash=hashlib.sha256(self.original).hexdigest())
            db.session.add(item); db.session.commit(); return item.id

    def upload(self,identifier,data):
        return self.client.post(f'/admin/recuperar-documento/{identifier}',data={'original':(io.BytesIO(data),'original.pdf')})

    def test_exact_original_restores_same_record_without_new_version(self):
        self.login('admin'); identifier=self.create_file()
        self.assertEqual(self.client.get('/admin/recuperar-documento?numero=0001/2026').status_code,200)
        self.assertEqual(self.upload(identifier,self.original).status_code,302)
        with app.app_context():
            item=db.session.get(Anexo,identifier)
            self.assertEqual(read_attachment_bytes(item),self.original)
            self.assertEqual(item.versao,8); self.assertEqual(item.storage_path,'fonte-preservada')
            self.assertEqual(Anexo.query.count(),1); self.assertTrue(verify_audit_chain(self.tenant)[0])
        self.assertEqual(self.upload(identifier,self.original).status_code,409)

    def test_different_bytes_and_other_clients_are_never_written(self):
        self.login('admin'); identifier=self.create_file(); foreign=self.create_file(self.foreign_tenant)
        self.assertEqual(self.upload(identifier,b'not-the-original').status_code,400)
        self.assertEqual(self.upload(foreign,self.original).status_code,404)
        with app.app_context(): self.assertIsNone(db.session.get(Anexo,identifier).file_data)
        self.login('protocolista')
        self.assertEqual(self.client.post(f'/admin/recuperar-documento/{identifier}',headers={'Content-Type':'application/json'}).status_code,403)

    def test_emission_evidence_and_missing_hash_prevent_recovery(self):
        self.login('admin'); identifier=self.create_file()
        with app.app_context():
            db.session.add(EmissaoEletronica(tenant_id=self.tenant,protocolo_id=self.pid,pdf_anexo_id=identifier,
                versao=1,emitido_por_id=self.ids['admin'],token_publico='recovery-fixture',codigo_publico='RECOVERY',
                pdf_sha256='0'*64,declaracao='Fictício',nome_emitente='Administrador',login_emitente='admin',
                ip_hash='x'*64,user_agent_hash='x'*64)); db.session.commit()
        self.assertEqual(self.upload(identifier,self.original).status_code,409)
        with app.app_context(): db.session.get(Anexo,identifier).file_hash=None; db.session.commit()
        self.assertEqual(self.upload(identifier,self.original).status_code,409)
