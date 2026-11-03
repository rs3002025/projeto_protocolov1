"""Indicadores de acervo não confundem data de negócio com regularização."""
import io
from datetime import date, datetime
from unittest import TestCase
from openpyxl import load_workbook
import test_multitenancy as _isolated
import test_protocol_workflow as fixture
import test_productivity as productivity_fixture
from app import app,db
from models import Protocolo,HistoricoProtocolo,Movimentacao


class HistoricalMetricsTests(TestCase):
    setUp=fixture.WorkflowTests.setUp
    tearDown=fixture.WorkflowTests.tearDown
    login=fixture.WorkflowTests.login
    send=fixture.WorkflowTests.send
    receive=fixture.WorkflowTests.receive
    participation=fixture.WorkflowTests.participation
    post=fixture.WorkflowTests.post
    context=productivity_fixture.ProductivityTests.context

    def report(self,start,end):
        return self.context(f'/relatorios/gestao?data_inicio={start}&data_fim={end}','relatorio_gestao.html')['report']

    def test_regularization_and_estimates_are_not_real_conclusions_or_average_samples(self):
        self.login('admin')
        with app.app_context():
            p=db.session.get(Protocolo,self.pid);p.data_solicitacao=date(2020,1,1)
            p.status='CONCLUÍDO';p.finalizado_em=datetime(2026,10,23,12)
            db.session.add(HistoricoProtocolo(tenant_id=self.tenant,protocolo_id=p.id,
                acao='FINALIZACAO',responsavel='Regularização do acervo',data_movimentacao=p.finalizado_em))
            estimated=Protocolo(tenant_id=self.tenant,numero='EST-2021',nome='Estimado',status='CONCLUÍDO',
                data_solicitacao=date(2021,1,1),finalizado_em=datetime(2021,12,31,3))
            db.session.add(estimated);db.session.flush();eid=estimated.id
            db.session.add(HistoricoProtocolo(tenant_id=self.tenant,protocolo_id=eid,
                acao='CONCLUSAO_ESTIMADA_ACERVO',data_movimentacao=estimated.finalizado_em))
            db.session.commit()
        current=self.report('2026-10-23','2026-10-23')
        self.assertEqual(current['conclusoes'],0)
        self.assertEqual(current['sem_data_conclusao'],1)
        prior=self.report('2021-01-01','2021-12-31')
        self.assertEqual(prior['conclusoes'],0);self.assertEqual(prior['conclusoes_estimadas'],1)
        self.assertIsNone(prior['media_dias']);self.assertEqual(prior['base_media'],0)
        self.assertEqual(sum(prior['chart']['estimadas']),1)
        workbook=load_workbook(io.BytesIO(self.client.get('/relatorios/gestao/excel?data_inicio=2021-01-01&data_fim=2021-12-31').data))
        self.assertEqual(list(workbook['Entradas e conclusões'].values)[-1],('2021-12-31',0,0,1))
        page=self.client.get(f'/protocolo/{eid}').get_data(as_text=True)
        self.assertIn('Data de conclusão estimada:',page)
        with app.app_context():
            p=db.session.get(Protocolo,eid);p.finalizado_em=datetime(2026,10,25,12)
            self.assertFalse(p.conclusao_estimada)

    def test_conclusion_in_period_includes_requests_opened_in_previous_years(self):
        self.login('admin')
        with app.app_context():
            p=db.session.get(Protocolo,self.pid);p.data_solicitacao=date(2025,1,1)
            p.status='CONCLUÍDO';p.finalizado_em=datetime(2026,10,3,2)
            db.session.commit()
        report=self.report('2026-10-02','2026-10-02')
        self.assertEqual(report['entradas'],0);self.assertEqual(report['conclusoes'],1)
        stats=self.client.get('/protocolos/dashboard-stats?dataInicio=2026-10-02&dataFim=2026-10-02').json
        self.assertEqual(stats['totalFinalizados'],1)
        self.assertEqual(stats['totalFinalizadosEstimados'],0)

    def test_receipt_state_is_preserved_but_unknown_historical_hours_do_not_enter_averages(self):
        self.login('admin');self.send('alice');self.receive('alice')
        part,first_id=self.participation('alice');self.send('carol',providencia_id=part)
        _,second_id=self.participation('carol');self.login('admin')
        with app.app_context():
            first=db.session.get(Movimentacao,first_id);second=db.session.get(Movimentacao,second_id)
            first.enviado_em=datetime(2026,10,1,3);first.recebido_em=datetime(2026,10,1,15)
            second.enviado_em=datetime(2026,10,2,15)
            db.session.add(HistoricoProtocolo(tenant_id=self.tenant,protocolo_id=self.pid,
                acao='TRAMITACAO_LEGADA',data_movimentacao=first.enviado_em))
            receipt=HistoricoProtocolo(tenant_id=self.tenant,protocolo_id=self.pid,
                acao='RECEBIMENTO',responsavel='Regularização do acervo',data_movimentacao=first.recebido_em)
            db.session.add(receipt);db.session.commit();rid=receipt.id
        report=self.report('2026-10-01','2026-10-01');sector=report['sectors'][0]
        self.assertEqual(sector['recebidos'],1);self.assertEqual(sector['pendentes'],0)
        self.assertIsNone(sector['espera_media']);self.assertIsNone(sector['atendimento_medio'])
        with app.app_context():
            db.session.delete(db.session.get(HistoricoProtocolo,rid));db.session.commit()
        sector=self.report('2026-10-01','2026-10-01')['sectors'][0]
        self.assertIsNone(sector['espera_media']);self.assertEqual(sector['atendimento_medio'],24)

    def test_regularization_does_not_replace_recent_real_activity(self):
        self.login('admin')
        with app.app_context():
            db.session.add(HistoricoProtocolo(tenant_id=self.tenant,protocolo_id=self.pid,
                acao='FINALIZACAO',responsavel='Regularização do acervo',data_movimentacao=datetime(2099,1,1)))
            db.session.commit()
        context=self.context('/home','home.html')
        self.assertFalse(any(h.responsavel=='Regularização do acervo' for h in context['workbench']['activity']))

    def test_dated_historical_closure_counts_by_day_without_inventing_hourly_service_time(self):
        self.login('admin')
        with app.app_context():
            p=db.session.get(Protocolo,self.pid);p.data_solicitacao=date(2026,10,1)
            p.status='CONCLUÍDO';p.finalizado_em=datetime(2026,10,2,3)
            db.session.add(HistoricoProtocolo(tenant_id=self.tenant,protocolo_id=p.id,
                acao='ARQUIVAMENTO_LEGADO',data_movimentacao=p.finalizado_em))
            db.session.add(Movimentacao(tenant_id=self.tenant,protocolo_id=p.id,
                setor_destino_id=self.sector,enviado_por_id=self.ids['admin'],
                enviado_em=datetime(2026,10,1,10),recebido_em=datetime(2026,10,1,12),recebido_por_id=self.ids['admin']))
            db.session.commit()
        report=self.report('2026-10-01','2026-10-02')
        self.assertEqual(report['conclusoes'],1);self.assertEqual(report['conclusoes_estimadas'],0)
        self.assertEqual(report['media_dias'],1)
        self.assertEqual(report['sectors'][0]['espera_media'],2)
        self.assertIsNone(report['sectors'][0]['atendimento_medio'])
