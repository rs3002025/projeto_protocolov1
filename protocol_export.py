"""Cópia de leitura do processo e pacote com originais, sem alterar documentos."""
import base64
import hashlib
import hmac
import io
import tempfile
import zipfile
from datetime import datetime, timezone

from flask import abort, current_app, render_template, request, send_file
from pypdf import PdfReader, PdfWriter
from sqlalchemy.orm import defer
from werkzeug.utils import secure_filename

MAX_FILES = 200
MAX_BYTES = 64 * 1024 * 1024
MAX_PAGES = 500


class ExportLimit(Exception):
    pass


def logo_data(organization):
    from app import normalize_logo_png
    if not organization.logo_data:
        return None
    image = normalize_logo_png(io.BytesIO(organization.logo_data)).getvalue()
    return 'data:image/png;base64,' + base64.b64encode(image).decode('ascii')


def render_section(template, **context):
    from weasyprint import HTML, URLFetcher
    return HTML(string=render_template(template, **context), url_fetcher=URLFetcher(
        allowed_protocols={'data'}, fail_on_errors=True)).write_pdf()


def current_attachments(attachments):
    selected = {}
    for item in sorted(attachments, key=lambda a: (a.versao, a.id)):
        if item.documento_chave in ('documento-protocolo', 'protocolo-autenticado'):
            continue
        key = item.documento_chave if item.documento_chave != 'anexo' else f'legado-{item.id}'
        selected[key] = item
    return sorted(selected.values(), key=lambda a: a.id)


def request_attachments(attachments):
    """Versões atuais anexadas ao envio, sem documentos de complementação."""
    return [item for item in current_attachments(attachments)
            if not item.solicitacao_complemento_id]


def readable_pdf(data, mime):
    """Só importa páginas estáticas; arquivos interativos ficam no pacote original."""
    if mime == 'application/pdf' or data[:5] == b'%PDF-':
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted or reader.get_fields():
            return None
        if not 0 < len(reader.pages) <= MAX_PAGES:
            raise ExportLimit('O documento ultrapassa o limite de 500 páginas por exportação.')
        return data
    if mime in ('image/jpeg', 'image/png', 'image/webp', 'image/tiff'):
        from PIL import Image, ImageOps
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 40_000_000 or getattr(image, 'n_frames', 1) != 1:
                return None
            image = ImageOps.exif_transpose(image)
            if image.mode in ('RGBA', 'LA') or 'transparency' in image.info:
                rgba = image.convert('RGBA')
                rgb = Image.new('RGB', image.size, 'white'); rgb.paste(rgba, mask=rgba.getchannel('A'))
            else:
                rgb = image.convert('RGB')
            rgb.thumbnail((2400, 3400))
            output = io.BytesIO(); rgb.save(output, format='PDF', resolution=150)
            return output.getvalue()
    return None


def assemble_process(protocol, organization):
    from app import (read_attachment_bytes, tenant_query, current_tenant_id, public_url,
                     chronological, history_parts, HISTORY_ACTION_LABELS, history_date_label,
                     history_observation_label, history_visible, history_actor_label)
    from models import Anexo, DespachoProtocolo, HistoricoProtocolo, Usuario

    tenant = current_tenant_id()
    attachments = tenant_query(Anexo).filter_by(protocolo_id=protocol.id).options(
        defer(Anexo.file_data)).order_by(Anexo.id).all()
    dispatches = tenant_query(DespachoProtocolo).filter_by(
        protocolo_id=protocol.id, excluido_em=None).options(defer(DespachoProtocolo.file_data)).order_by(DespachoProtocolo.numero).all()
    current = current_attachments(attachments)
    if len(current) + len(dispatches) + 1 > MAX_FILES:
        raise ExportLimit('O processo ultrapassa o limite de 200 arquivos por exportação.')
    history = tenant_query(HistoricoProtocolo).filter_by(protocolo_id=protocol.id).limit(10001).all()
    if len(history) > 10000:
        raise ExportLimit('O processo ultrapassa o limite de 10.000 eventos por exportação.')
    actors = Usuario.query.filter(Usuario.id.in_([h.usuario_id for h in history if h.usuario_id]),
        (Usuario.tenant_id == tenant) | Usuario.is_platform_admin.is_(True)).all()
    names = {u.id: u.nome_completo or u.nome for u in actors}
    timeline = []
    for item in chronological(history):
        if not history_visible(item):
            continue
        parts = history_parts(item)
        timeline.append(dict(title=HISTORY_ACTION_LABELS.get(item.acao, 'Atualização'),
            date=history_date_label(item), actor=history_actor_label(item, names),
            status=item.status, system=parts['sistema'],
            note=history_observation_label(parts['observacao']) if parts['observacao'] else ''))
    context = dict(protocolo=protocol, organizacao=organization, pdf_logo_url=logo_data(organization),
                   generated_at=datetime.now(timezone.utc), timeline=timeline)
    originals, content, total = [], [], 0

    def read(item):
        nonlocal total
        if item.tenant_id != tenant or item.protocolo_id != protocol.id:
            raise RuntimeError('Documento incompatível com o processo.')
        if getattr(item, 'file_size', 0) > MAX_BYTES - total:
            raise ExportLimit('Os arquivos ultrapassam 64 MB por exportação.')
        data = read_attachment_bytes(item)
        total += len(data)
        if total > MAX_BYTES:
            raise ExportLimit('Os arquivos ultrapassam 64 MB por exportação.')
        return data

    def add_document(title, data, mime, path):
        originals.append((path, data))
        try:
            pdf = readable_pdf(data, mime)
        except ExportLimit:
            raise
        except Exception:
            pdf = None  # O original íntegro é preservado, mesmo sem conversão.
        if pdf is None:
            pdf = render_section('processo_exportacao.html', section='original',
                                 document_title=title, original_path=path, **context)
        content.append((title, pdf))

    emission = protocol.emissao_eletronica
    request_doc = emission.pdf_anexo if emission else next((a for a in sorted(
        attachments, key=lambda a: (a.versao, a.id), reverse=True)
        if a.documento_chave == 'documento-protocolo'), None)
    if request_doc:
        data = read(request_doc)
        if emission and not hmac.compare_digest(hashlib.sha256(data).hexdigest(), emission.pdf_sha256):
            raise RuntimeError('Integridade do requerimento não confirmada.')
    else:
        import qrcode
        qr = io.BytesIO(); qrcode.make(public_url('consulta_publica',
            consulta_token=protocol.consulta_token)).save(qr, format='PNG')
        data = render_section('pdf_template.html', emissao=None, qr_validacao_url=None,
            qr_code_url='data:image/png;base64,'+base64.b64encode(qr.getvalue()).decode('ascii'), **context)
    add_document('Pedido', data, 'application/pdf', 'originais/01-pedido.pdf')
    content.append(('Tramitação', render_section('processo_exportacao.html', section='history', **context)))
    for index, dispatch in enumerate(dispatches, 1):
        add_document(f'Despacho {dispatch.numero:03d} - {dispatch.assunto or "Sem assunto"}',
            read(dispatch), 'application/pdf',
            f'originais/despachos/{index:03d}-{secure_filename(dispatch.file_name) or "despacho.pdf"}')
    for index, attachment in enumerate(current, 1):
        add_document(f'Anexo {index:03d} - {attachment.file_name}', read(attachment), attachment.mime_type,
            f'originais/anexos/{index:03d}-{secure_filename(attachment.file_name) or "arquivo"}')
    index_rows = [title for title, _ in content]
    cover = render_section('processo_exportacao.html', section='cover', contents=index_rows,
                           dispatch_count=len(dispatches), attachment_count=len(current), **context)
    writer = PdfWriter()
    for title, data in [('Capa e índice', cover)] + content:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if len(writer.pages) + len(reader.pages) > MAX_PAGES:
            raise ExportLimit('O processo ultrapassa o limite de 500 páginas por exportação.')
        writer.append(reader, outline_item=title, import_outline=False, excluded_fields=['/Annots','/AA','/B'])
    writer.add_metadata({'/Title':f'Processo {protocol.numero}', '/Author':organization.nome,
                         '/Subject':'Cópia de leitura do processo'})
    pdf = io.BytesIO(); writer.write(pdf)
    return pdf.getvalue(), originals


def register_export_routes(app):
    from app import accessible_protocol_or_404, active_organization, permission_required

    @app.get('/protocolo/<int:protocolo_id>/processo/baixar')
    @permission_required('view')
    def baixar_processo(protocolo_id):
        protocol = accessible_protocol_or_404(protocolo_id)
        kind = request.args.get('formato', 'zip')
        if kind not in ('pdf','zip'):
            abort(400, description='Formato de exportação inválido.')
        try:
            pdf, originals = assemble_process(protocol, active_organization())
        except ExportLimit as exc:
            abort(422, description=str(exc))
        except Exception:
            current_app.logger.exception('Falha ao exportar processo %s.', protocol.id)
            abort(503, description='Não foi possível reunir todos os arquivos do processo. Tente novamente; nenhum pacote incompleto foi gerado.')
        name = secure_filename('processo-' + protocol.numero) or 'processo'
        output = tempfile.SpooledTemporaryFile(max_size=8*1024*1024)
        if kind == 'pdf':
            output.write(pdf)
        else:
            with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as package:
                package.writestr(name+'.pdf', pdf)
                for path, data in originals:
                    package.writestr(path, data)
                package.writestr('LEIA-ME.txt',
                    'PROCESSO COMPLETO\n\nO PDF reúne capa, pedido, tramitação, despachos e anexos compatíveis. '
                    'O índice e os marcadores do PDF ajudam na navegação.\n\n'
                    'Planilhas, arquivos interativos, protegidos ou não compatíveis estão na pasta originais. '
                    'O pacote inclui os documentos atuais; versões substituídas permanecem preservadas no sistema.\n\n'
                    'O PDF compilado é uma cópia para leitura. Para conferir assinaturas digitais, use os arquivos '
                    'originais, preservados sem alteração. O pacote retrata a situação no momento do download.\n')
        output.seek(0)
        response = send_file(output, mimetype='application/pdf' if kind=='pdf' else 'application/zip',
                             as_attachment=True, download_name=f'{name}.{kind}', max_age=0)
        response.headers['Cache-Control'] = 'private, no-store'
        response.call_on_close(output.close)
        return response
