"""Exportação com banco isolado e PDFs sintéticos; sem serviços remotos."""
import hashlib
import io
import zipfile
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch

import test_multitenancy as _isolated_database_setup
import test_protocol_workflow as workflow_fixture
from flask import render_template, template_rendered
from pypdf import PdfReader, PdfWriter
from app import app, db
from models import Anexo, DespachoProtocolo, HistoricoProtocolo, Protocolo, Usuario
from protocol_export import readable_pdf


def pdf_bytes(width=400):
    writer=PdfWriter(); writer.add_blank_page(width=width,height=600)
    output=io.BytesIO(); writer.write(output); return output.getvalue()


class ProcessExportTests(TestCase):
    setUp = workflow_fixture.WorkflowTests.setUp
    tearDown = workflow_fixture.WorkflowTests.tearDown
    login = workflow_fixture.WorkflowTests.login

    def attachment(self, name='pedido.pdf', key='documento-protocolo', data=None, version=1, mime='application/pdf'):
        data=pdf_bytes() if data is None else data
        with app.app_context():
            item=Anexo(tenant_id=self.tenant,protocolo_id=self.pid,file_name=name,documento_chave=key,
                versao=version,storage_backend='database',storage_path='never-read-from-disk',
                file_hash=hashlib.sha256(data).hexdigest(),file_data=data,file_size=len(data),mime_type=mime)
            db.session.add(item); db.session.commit(); return item.id

    def section(self, template, **context):
        # Confere o template real sem exigir bibliotecas nativas do WeasyPrint no Windows.
        html=render_template(template,**context)
        self.assertNotIn('<script>alert(1)</script>',html)
        return pdf_bytes({'cover':200,'history':300,'original':350}.get(context.get('section'),400))

    def export(self, kind='zip'):
        with patch('protocol_export.render_section',side_effect=self.section), patch('app.bucket_client',return_value=None):
            return self.client.get(f'/protocolo/{self.pid}/processo/baixar?formato={kind}')

    def test_package_order_original_bytes_and_no_database_mutations(self):
        self.login('admin'); self.attachment()
        previous=b'old spreadsheet'; current=b'new spreadsheet'
        old_id=self.attachment('planilha.xlsx','planilha',previous,mime='application/octet-stream')
        self.attachment('planilha.xlsx','planilha',current,version=2,mime='application/octet-stream')
        self.attachment('relatorio.pdf','relatorio',pdf_bytes(600))
        with app.app_context():
            data=pdf_bytes(500)
            db.session.add(DespachoProtocolo(tenant_id=self.tenant,protocolo_id=self.pid,numero=1,
                protocolo_numero='0001/2026',texto='Despacho fictício',assunto='Análise',
                autor_id=self.ids['admin'],autor_nome='Administrador fictício',criado_em=datetime.now(timezone.utc),
                envio_token='export-test',file_name='despacho.pdf',storage_path='test',storage_backend='database',
                file_data=data,file_hash=hashlib.sha256(data).hexdigest()))
            db.session.commit(); before=(Anexo.query.count(),HistoricoProtocolo.query.count())
        response=self.export()
        self.assertEqual(response.status_code,200)
        self.assertIn('attachment;',response.headers['Content-Disposition'])
        self.assertIn('no-store',response.headers['Cache-Control'])
        with zipfile.ZipFile(io.BytesIO(response.data)) as package:
            names=package.namelist()
            self.assertTrue(all(not n.startswith('/') and '..' not in n.split('/') for n in names))
            self.assertEqual(package.read('originais/01-pedido.pdf'),pdf_bytes())
            self.assertEqual(package.read(f'originais/anteriores/{old_id:06d}-planilha.xlsx'),previous)
            self.assertTrue(any(package.read(n)==current for n in names if n.startswith('originais/anexos/')))
            reader=PdfReader(io.BytesIO(package.read('processo-0001_2026.pdf')))
            self.assertEqual([int(p.mediabox.width) for p in reader.pages],[200,400,300,500,350,600])
            self.assertEqual(len(reader.outline),6)
        with app.app_context():
            self.assertEqual((Anexo.query.count(),HistoricoProtocolo.query.count()),before)

    def test_permissions_and_tenant_boundary_before_reading_files(self):
        for who in ('admin','protocolista','consulta','alice'):
            self.login(who)
            with patch('protocol_export.assemble_process',return_value=(pdf_bytes(),[])) as build:
                self.assertEqual(self.client.get(f'/protocolo/{self.pid}/processo/baixar?formato=pdf').status_code,200)
                self.assertEqual(self.client.get(f'/protocolo/{self.foreign_pid}/processo/baixar').status_code,404)
                self.assertEqual(build.call_count,1)
        self.login('carol')
        with patch('protocol_export.assemble_process') as build:
            self.assertEqual(self.client.get(f'/protocolo/{self.pid}/processo/baixar').status_code,404)
            build.assert_not_called()
        self.login('admin')
        self.assertEqual(self.client.get(f'/protocolo/{self.pid}/processo/baixar?formato=exe').status_code,400)

    def test_unavailable_or_tampered_document_never_returns_partial_package(self):
        self.login('admin'); aid=self.attachment()
        with app.app_context():
            db.session.get(Anexo,aid).file_data=b'alterado'; db.session.commit()
        self.assertEqual(self.export().status_code,503)
        with app.app_context():
            db.session.get(Anexo,aid).file_data=None; db.session.commit()
        self.assertEqual(self.export().status_code,503)

    def test_timeline_is_chronological_and_escapes_free_text(self):
        self.login('admin'); self.attachment()
        with app.app_context():
            now=datetime.now(timezone.utc)
            db.session.add_all([HistoricoProtocolo(tenant_id=self.tenant,protocolo_id=self.pid,
                acao='TRAMITACAO',status='EM TRAMITAÇÃO',observacao='<script>alert(1)</script>',
                data_movimentacao=now-timedelta(days=2)),
                HistoricoProtocolo(tenant_id=self.tenant,protocolo_id=self.pid,acao='RECEBIMENTO',
                    status='RECEBIDO',observacao='Depois',data_movimentacao=now-timedelta(days=1))]); db.session.commit()
        with patch('protocol_export.render_section',side_effect=self.section) as render:
            self.assertEqual(self.client.get(f'/protocolo/{self.pid}/processo/baixar?formato=pdf').status_code,200)
            timeline=next(c.kwargs['timeline'] for c in render.call_args_list if c.kwargs.get('section')=='history')
            self.assertEqual([e['title'] for e in timeline],['Encaminhamento','Recebimento'])

    def test_limits_and_deleted_protocol(self):
        self.login('admin'); self.attachment()
        with patch('protocol_export.MAX_BYTES',1):
            self.assertEqual(self.export().status_code,422)
        with patch('protocol_export.MAX_PAGES',1):
            self.assertEqual(self.export().status_code,422)
        with app.app_context():
            db.session.get(Protocolo,self.pid).excluido_em=datetime.now(timezone.utc); db.session.commit()
        self.assertEqual(self.export().status_code,404)

    def test_image_is_readable_and_other_formats_stay_original(self):
        from PIL import Image
        data=io.BytesIO(); Image.new('RGB',(100,100),'white').save(data,format='PNG')
        self.assertEqual(len(PdfReader(io.BytesIO(readable_pdf(data.getvalue(),'image/png'))).pages),1)
        self.assertIsNone(readable_pdf(b'Excel ficticio','application/octet-stream'))
        writer=PdfWriter(); writer.add_blank_page(width=100,height=100); writer.encrypt('test-only')
        locked=io.BytesIO(); writer.write(locked)
        self.assertIsNone(readable_pdf(locked.getvalue(),'application/pdf'))

    def test_report_summary_uses_all_filtered_pages_and_current_sector(self):
        self.login('admin')
        with app.app_context():
            db.session.add_all([Protocolo(tenant_id=self.tenant,numero=f'EX-{i}',nome='Fictício',
                status='EM ANÁLISE',setor_atual_id=self.sector) for i in range(13)])
            db.session.commit()
        contexts=[]
        def capture(sender,template,context,**extra):
            if template.name=='relatorios.html': contexts.append(context)
        with template_rendered.connected_to(capture,app):
            response=self.client.get('/relatorios?setor_atual=SEFIN&page=2')
        self.assertEqual(response.status_code,200)
        self.assertEqual(contexts[0]['resumo']['total'],14)
        self.assertEqual(contexts[0]['resumo']['abertos'],14)
        self.assertEqual(len(contexts[0]['protocolos'].items),4)

    def test_pdf_copy_drops_active_annotations_but_zip_keeps_original(self):
        from pypdf.generic import NameObject, DictionaryObject, ArrayObject, TextStringObject
        self.login('admin'); self.attachment()
        writer=PdfWriter(); page=writer.add_blank_page(width=600,height=600)
        writer.add_js('app.alert("fixture")')
        annotation=DictionaryObject({NameObject('/Type'):NameObject('/Annot'),
            NameObject('/Subtype'):NameObject('/Link'),NameObject('/A'):DictionaryObject({
                NameObject('/S'):NameObject('/JavaScript'),NameObject('/JS'):TextStringObject('app.alert("fixture")')})})
        page[NameObject('/Annots')]=ArrayObject([writer._add_object(annotation)])
        original=io.BytesIO(); writer.write(original)
        self.attachment('anexo.pdf','anexo-ativo',original.getvalue())
        response=self.export()
        self.assertEqual(response.status_code,200)
        with zipfile.ZipFile(io.BytesIO(response.data)) as package:
            self.assertEqual(package.read('originais/anexos/001-anexo.pdf'),original.getvalue())
            combined=PdfReader(io.BytesIO(package.read('processo-0001_2026.pdf')))
            self.assertFalse(any('/Annots' in page for page in combined.pages))
            self.assertNotIn('/JavaScript',combined.trailer['/Root'].get('/Names',{}))
