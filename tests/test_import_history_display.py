"""Presentation tests only; SQLite and fictitious records."""
import os,unittest
from datetime import datetime
from types import SimpleNamespace
os.environ['DATABASE_URL']='sqlite:///:memory:'
os.environ['SECRET_KEY']='isolated-history-presentation-tests'
os.environ['TENANT_SUBDOMAINS_ENABLED']='false'
from app import app,history_parts,history_date_label,history_observation_label,HISTORY_ACTION_LABELS

class ImportPresentationTests(unittest.TestCase):
    def test_imported_legacy_note_is_not_rewritten_or_displayed(self):
        original='Importação do relatório histórico. Tabela 1, linha 2. Número original: 966/2026. Não representa recebimento.'
        e=SimpleNamespace(acao='IMPORTACAO_LEGADO',observacao=original)
        self.assertEqual(history_parts(e),{'sistema':'','observacao':''})
        self.assertEqual(history_observation_label(original,e.acao),'')
        self.assertEqual(e.observacao,original)
        self.assertEqual(HISTORY_ACTION_LABELS[e.acao],'Importado')

    def test_normal_observation_is_preserved(self):
        e=SimpleNamespace(acao='ALTERACAO_STATUS',observacao='Observação informada pelo usuário.')
        self.assertEqual(history_parts(e)['observacao'],e.observacao)
        self.assertEqual(history_observation_label(e.observacao,e.acao),e.observacao)

    def test_source_date_has_no_fabricated_hour(self):
        e=SimpleNamespace(acao='TRAMITACAO_LEGADA',data_movimentacao=datetime(2026,1,5,3))
        self.assertEqual(history_date_label(e),'05/01/2026')

    def test_actual_system_event_keeps_brasilia_time(self):
        e=SimpleNamespace(acao='TRAMITACAO',data_movimentacao=datetime(2026,1,5,13,15))
        self.assertEqual(history_date_label(e),'05/01/2026 às 10:15')

    def test_changed_templates_compile(self):
        with app.app_context():
            for path in ('protocolo_detalhe.html','portal_detalhe.html','consulta_publica.html'):
                app.jinja_env.get_template(path)
if __name__=='__main__':unittest.main()
