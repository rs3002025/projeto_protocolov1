"""Abre páginas e consultas reais para cada perfil, com dados inteiramente fictícios."""
from unittest import TestCase
import test_multitenancy as isolated
import test_protocol_workflow as fixture
from app import app


class ToolPageTests(TestCase):
    setUp = fixture.WorkflowTests.setUp
    tearDown = fixture.WorkflowTests.tearDown
    login = fixture.WorkflowTests.login

    def test_available_pages_and_json_queries_by_role(self):
        pages = ['/home', '/protocolos', '/meus_protocolos', '/relatorios', '/modelos-despacho',
                 '/pendencias-recebimento', '/suporte', '/configuracoes', '/admin/auditoria',
                 '/admin/servidores/cadastro-portal', f'/protocolo/{self.pid}',
                 f'/protocolo/{self.pid}/editar', f'/protocolo/{self.pid}/despachos/novo']
        apis = ['/api/usuarios', '/api/lotacoes', '/api/tipos_requerimento', '/api/bairros',
                '/api/servidores/search?nome=QA', '/api/servidor/QA-INEXISTENTE',
                '/protocolos/ultimoNumero/2026', f'/api/protocolo/{self.pid}',
                '/protocolos/dashboard-stats', '/protocolos/dashboard-stats?dataInicio=invalida']
        for role in ('admin', 'protocolista', 'alice', 'consulta', 'foreign'):
            self.login(role)
            for path in pages:
                with self.subTest(role=role, path=path):
                    response = self.client.get(path)
                    self.assertIn(response.status_code, (200, 302, 403, 404))
                    if role == 'admin':
                        self.assertEqual(response.status_code, 200)
            for path in apis:
                with self.subTest(role=role, path=path):
                    response = self.client.get(path, headers={'Accept': 'application/json'})
                    self.assertIn(response.status_code, (200, 400, 403, 404))
                    self.assertTrue(response.is_json)

    def test_unauthenticated_queries_return_json_and_pages_require_login(self):
        for path in ('/api/usuarios', '/api/lotacoes', '/protocolos/dashboard-stats'):
            response = self.client.get(path, headers={'Accept': 'application/json'})
            self.assertEqual(response.status_code, 401)
            self.assertFalse(response.json['sucesso'])
        self.assertEqual(self.client.get('/protocolos').status_code, 302)
