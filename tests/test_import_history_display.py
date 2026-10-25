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

    def test_old_document_events_hide_internal_keys_without_rewriting_audit(self):
        cases=[('DOCUMENTO_GERADO','protocolo_0001-2026_v8.pdf — versão 8.','Requerimento disponibilizado.'),
               ('ANEXO_ADICIONADO','atestado.pdf — versão 1. Documento internal-document-key.','Documento anexado: atestado.pdf.'),
               ('NOVA_VERSAO_DOCUMENTO','planilha.xlsx — versão 2. Documento internal-document-key.','Documento substituído: planilha.xlsx.')]
        for action,original,label in cases:
            event=SimpleNamespace(acao=action,observacao=original)
            self.assertEqual(history_parts(event),{'sistema':label,'observacao':''})
            self.assertEqual(event.observacao,original)

    def test_old_forwarding_phrases_are_hidden_without_changing_audit(self):
        cases = [
            ('Intervenção da equipe de protocolo. Encaminhado para SEAD, disponível a todos do setor.  deferido pela seduc', 'Encaminhado para SEAD.', 'deferido pela seduc'),
            ('Encaminhado para SEAGRI, disponível a todos do setor. Transferência administrativa do encaminhamento de SEDUCTEC. resolvido', 'Encaminhado para SEAGRI.', 'resolvido'),
            ('Encaminhado para SEFIN, aos cuidados de Maria. Transferência administrativa do encaminhamento de SEAD. Responsabilidade transferida de João. Parecer recebido.\nPróxima etapa.', 'Encaminhado para SEFIN — Maria.', 'Parecer recebido.\nPróxima etapa.'),
            ('Encaminhado para SEAD, disponível a todos do setor.', 'Encaminhado para SEAD.', ''),
        ]
        for original, heading, note in cases:
            with self.subTest(original=original):
                e = SimpleNamespace(acao='TRAMITACAO', observacao=original)
                self.assertEqual(history_parts(e), {'sistema': heading, 'observacao': note})
                self.assertEqual(e.observacao, original)

    def test_new_forwarding_keeps_user_text_verbatim(self):
        note = 'Transferência administrativa do encaminhamento de exemplo.\nTexto disponível a todos do setor.\n\nOutro parágrafo.'
        e = SimpleNamespace(acao='TRAMITACAO', observacao='Encaminhado para Sec. Educação — Maria A. Silva.\n\n' + note)
        self.assertEqual(history_parts(e), {'sistema':'Encaminhado para Sec. Educação — Maria A. Silva.', 'observacao':note})
        e = SimpleNamespace(acao='TRAMITACAO', observacao='Encaminhado para SEAD.')
        self.assertEqual(history_parts(e), {'sistema':'Encaminhado para SEAD.', 'observacao':''})

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
