"""Cadastros de lista: repetição, inativos, isolamento e entradas inválidas."""
from unittest import TestCase
import test_multitenancy as isolated
import test_protocol_workflow as fixture
from app import app,db
from models import Lotacao,TipoRequerimento,AuditoriaEvento


class ListRegistrationTests(TestCase):
    setUp=fixture.WorkflowTests.setUp
    tearDown=fixture.WorkflowTests.tearDown
    login=fixture.WorkflowTests.login

    def test_duplicate_inactive_and_foreign_names_do_not_cause_500(self):
        self.login('admin')
        for kind,model in [('tipo',TipoRequerimento),('lotacao',Lotacao)]:
            with self.subTest(kind=kind):
                path=f'/admin/item/{kind}/novo'
                self.assertEqual(self.client.post(path,data={'nome':'QA Cadastro'}).status_code,302)
                for name in ('QA Cadastro',' qa cadastro '):
                    response=self.client.post(path,data={'nome':name},follow_redirects=True)
                    self.assertEqual(response.status_code,200)
                    self.assertIn('Já existe',response.get_data(as_text=True))
                with app.app_context():
                    item=model.query.filter_by(tenant_id=self.tenant,nome='QA Cadastro').one()
                    item.ativo=False;db.session.commit()
                response=self.client.post(path,data={'nome':'QA Cadastro'},follow_redirects=True)
                self.assertIn('Reative o cadastro existente',response.get_data(as_text=True))
                with app.app_context():
                    self.assertFalse(model.query.filter_by(tenant_id=self.tenant,nome='QA Cadastro').one().ativo)
                    db.session.add(model(tenant_id=self.foreign_tenant,nome='Exclusivo externo',ativo=True));db.session.commit()
                self.assertEqual(self.client.post(path,data={'nome':'Exclusivo externo'}).status_code,302)
                with app.app_context():
                    self.assertEqual(model.query.filter_by(nome='Exclusivo externo').count(),2)
                    self.assertEqual(model.query.filter_by(tenant_id=self.tenant,nome='QA Cadastro').count(),1)

    def test_invalid_input_or_profile_does_not_create_records(self):
        self.login('admin')
        for name in ('', ' ', 'x'*181, 'nome\x00inválido'):
            self.assertEqual(self.client.post('/admin/item/tipo/novo',data={'nome':name}).status_code,302)
        self.assertEqual(self.client.post('/admin/item/desconhecido/novo',data={'nome':'QA'}).status_code,404)
        self.login('consulta')
        self.assertIn(self.client.post('/admin/item/tipo/novo',data={'nome':'Sem permissão'}).status_code,(302,403))
        with app.app_context():
            self.assertEqual(TipoRequerimento.query.count(),0)
