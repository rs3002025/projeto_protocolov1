"""Painel com banco isolado e dados fictícios; não usa ambientes remotos."""
from datetime import date, timedelta
from unittest import TestCase
from unittest.mock import patch
from flask import template_rendered
from sqlalchemy import event
from sqlalchemy.dialects import postgresql

import test_multitenancy as _isolated_database_setup
import test_protocol_workflow as workflow_fixture
from app import app, db, apply_protocol_filters
from models import (Protocolo, Lotacao, Usuario, AcompanhamentoProtocolo, ProvidenciaProtocolo,
                    HistoricoProtocolo, SolicitacaoComplemento)


class WorkbenchTests(TestCase):
    setUp = workflow_fixture.WorkflowTests.setUp
    tearDown = workflow_fixture.WorkflowTests.tearDown
    login = workflow_fixture.WorkflowTests.login
    post = workflow_fixture.WorkflowTests.post
    send = workflow_fixture.WorkflowTests.send
    participation = workflow_fixture.WorkflowTests.participation
    receive = workflow_fixture.WorkflowTests.receive

    def view(self, query=''):
        contexts = []
        def capture(sender, template, context, **extra):
            if template.name == 'home.html': contexts.append(context)
        with template_rendered.connected_to(capture, app):
            response = self.client.get('/home' + query)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True)[:500])
        return contexts[0]['workbench'], response.get_data(as_text=True)

    def test_team_summary_excludes_other_clients_closed_and_deleted(self):
        self.login('admin')
        with app.app_context():
            db.session.add_all([
                Protocolo(tenant_id=self.tenant, numero='FECHADO', nome='Fechado', status='FINALIZADO'),
                Protocolo(tenant_id=self.tenant, numero='ARQUIVADO', nome='Arquivado', status='ARQUIVADO'),
            ]); db.session.commit()
        wb, html = self.view()
        self.assertEqual(wb['counts']['prioridades'], 1)
        self.assertNotIn('Outro cliente', html)
        self.assertIn('Fila da equipe', html)
        self.assertIn('data-dashboard-analytics', html)

    def test_parallel_receipts_count_protocol_once_and_followers_are_not_owners(self):
        self.login('admin'); self.send('alice','carol')
        wb, _ = self.view('?fila=receber')
        self.assertEqual(wb['counts']['receber'], 1)
        self.assertEqual(len(wb['rows']), 1)
        self.post('acompanhar', {'acompanhar':'1'})
        wb, _ = self.view('?escopo=meu&fila=comigo')
        self.assertEqual(wb['counts']['comigo'], 0)
        self.assertEqual(wb['counts']['acompanhar'], 1)
        self.receive('alice')
        wb, _ = self.view()
        self.assertEqual(wb['scope'], 'meu')
        self.assertEqual(wb['counts']['comigo'], 1)
        self.assertEqual(wb['counts']['receber'], 0)
        self.assertEqual(self.client.get('/home?escopo=equipe').status_code, 403)

    def test_replaced_destination_is_not_pending_on_dashboard(self):
        self.login('admin'); self.send('alice')
        self.send('carol')
        self.login('alice')
        wb, _ = self.view('?fila=receber')
        self.assertEqual(wb['counts']['receber'], 0)
        self.assertEqual(wb['counts']['comigo'], 0)
        self.login('carol')
        wb, _ = self.view('?fila=receber')
        self.assertEqual(wb['counts']['receber'], 1)

    def test_deadlines_use_brasilia_date_and_never_include_closed_records(self):
        self.login('admin')
        today = date(2026,10,24)
        with app.app_context():
            p = db.session.get(Protocolo, self.pid); p.prazo_em = today - timedelta(days=1)
            db.session.add_all([
                Protocolo(tenant_id=self.tenant, numero='HOJE', nome='Prazo hoje', status='RECEBIDO', prazo_em=today),
                Protocolo(tenant_id=self.tenant, numero='FECHADO', nome='Fechado', status='CONCLUÍDO', prazo_em=today - timedelta(days=2)),
            ]); db.session.commit()
        with patch('dashboard_workbench.today_brasilia', return_value=today):
            wb, _ = self.view('?fila=atrasados')
        self.assertEqual(wb['counts']['atrasados'], 1)
        self.assertEqual(wb['counts']['prazos'], 1)
        self.assertEqual(wb['deadlines'][0].numero, 'HOJE')
        self.assertEqual(wb['rows'][0]['urgency'], 'late')

    def test_readonly_role_has_no_receiving_controls(self):
        self.login('consulta')
        wb, html = self.view()
        self.assertFalse(wb['can_route'])
        self.assertNotIn('Conferir recebimento', html)
        self.assertNotIn('Novo protocolo</a>', html)
        self.assertEqual(self.client.get('/home?fila=receber').status_code, 400)
        self.assertEqual(self.client.get('/home?fila=concluir').status_code, 400)

    def test_formal_document_request_overrides_received_for_analysis_queue(self):
        self.login('admin')
        with app.app_context():
            p=db.session.get(Protocolo,self.pid); p.status='RECEBIDO'
            db.session.add(SolicitacaoComplemento(tenant_id=self.tenant,protocolo_id=p.id,
                solicitado_por_id=self.ids['admin'],motivo='Documento fictício pendente',status='PENDENTE'))
            db.session.commit()
        wb,_=self.view()
        self.assertEqual(wb['counts']['documentos'],1)
        self.assertEqual(wb['counts']['analisar'],0)

    def test_initial_receipt_and_automatic_receipt_have_distinct_queues(self):
        self.login('admin')
        with app.app_context():
            p=db.session.get(Protocolo,self.pid); p.modalidade_abertura='remota_requerente'; p.status='AGUARDANDO RECEBIMENTO'
            db.session.commit()
        wb,_=self.view()
        self.assertEqual(wb['counts']['receber'],1)
        with app.app_context():
            p=db.session.get(Protocolo,self.pid); p.status='RECEBIDO'
            db.session.add(HistoricoProtocolo(tenant_id=self.tenant,protocolo_id=p.id,
                acao='RECEBIMENTO_AUTOMATICO',status='RECEBIDO',observacao='Registro fictício'))
            db.session.commit()
        wb,_=self.view()
        self.assertEqual(wb['counts']['receber'],0)
        self.assertEqual(wb['counts']['analisar'],1)

    def test_invalid_queue_scope_page_and_analytics_dates_are_rejected(self):
        self.login('admin')
        for query in ('?fila=invalid','?escopo=outro','?pagina=-1','?pagina=NaN'):
            self.assertEqual(self.client.get('/home'+query).status_code, 400)
        for query in ('?dataInicio=not-a-date','?dataInicio=2026-10-24&dataFim=2026-10-01','?evolucaoPeriodo=invalid'):
            self.assertEqual(self.client.get('/protocolos/dashboard-stats'+query).status_code, 400)

    def test_queue_is_paginated_and_distribution_counts_unique_protocols(self):
        self.login('admin')
        with app.app_context():
            db.session.add_all([Protocolo(tenant_id=self.tenant,numero=f'FICTICIO-{i}',nome=f'Fictício {i}',status='EM ANÁLISE') for i in range(10)])
            db.session.commit()
        wb, _ = self.view()
        self.assertEqual(len(wb['rows']),8)
        self.assertEqual(wb['pagination'].total,11)
        self.assertEqual(sum(item['count'] for item in wb['distribution']),11)
        self.assertIsNotNone(wb['next_url'])

    def test_sector_analytics_include_pending_parallel_destinations_and_history_before_2025(self):
        self.login('admin'); self.send('alice','carol')
        with app.app_context():
            p = db.session.get(Protocolo,self.pid); p.data_solicitacao=date(1992,1,4)
            other_sector = db.session.get(Usuario,self.ids['carol']).lotacao.nome
            db.session.commit()
        response = self.client.get('/protocolos/dashboard-stats?evolucaoPeriodo=all')
        self.assertEqual(response.status_code,200)
        data=response.json
        self.assertEqual(sum(item['total'] for item in data['statusProtocolos']),1)
        self.assertEqual({item['setor'] for item in data['setorProtocolos']},{'SEFIN',other_sector})
        self.assertTrue(any(item['intervalo'].startswith('1992') for item in data['evolucaoProtocolos']))
        filtered=self.client.get('/protocolos/dashboard-stats',query_string={'lotacao':other_sector,'evolucaoPeriodo':'all'})
        self.assertEqual(filtered.status_code,200)
        self.assertEqual(filtered.json['setorProtocolos'],[{'setor':other_sector,'total':1}])
        self.assertIn('0001/2026',self.client.get('/protocolos',query_string={'setor_atual':other_sector}).get_data(as_text=True))

    def test_postgresql_queries_compile_without_correlated_aggregate_errors(self):
        self.login('admin'); self.send('alice','carol')
        statements=[]
        def capture(conn,cursor,statement,parameters,context,executemany):
            if context.compiled:
                statements.append(str(context.compiled.statement.compile(dialect=postgresql.dialect())))
        with app.app_context(): engine=db.engine; event.listen(engine,'before_cursor_execute',capture)
        try: self.view()
        finally: event.remove(engine,'before_cursor_execute',capture)
        self.assertTrue(statements)

    def test_template_escapes_requester_text(self):
        self.login('admin')
        with app.app_context():
            db.session.get(Protocolo,self.pid).nome='<script>alert(1)</script>'; db.session.commit()
        _,html=self.view()
        self.assertNotIn('<script>alert(1)</script>',html)
        self.assertIn('&lt;script&gt;',html)
