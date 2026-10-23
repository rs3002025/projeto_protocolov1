"""Despachos formais, separados das observações de encaminhamento."""
import base64
import io
import re
from datetime import datetime, timezone

from flask import abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user
from sqlalchemy import func
from werkzeug.utils import secure_filename
from dispatch_rich_text import dispatch_body, normalize_delta

MAX_DISPATCH_LENGTH = 100_000


def render_dispatch_pdf(despacho, organizacao):
    from weasyprint import HTML, URLFetcher
    from app import normalize_logo_png

    # O PDF não depende de uma chamada HTTP ao próprio serviço nem carrega
    # endereços fornecidos no texto. A marca é incorporada ao documento.
    logo = None
    if organizacao.logo_data:
        data = normalize_logo_png(io.BytesIO(organizacao.logo_data)).getvalue()
        logo = 'data:image/png;base64,' + base64.b64encode(data).decode('ascii')
    html = render_template('despacho_pdf.html', despacho=despacho,
                           organizacao=organizacao, pdf_logo_url=logo,
                           dispatch_body=dispatch_body)

    return HTML(string=html, url_fetcher=URLFetcher(
        allowed_protocols={'data'}, fail_on_errors=True)).write_pdf()


def register_dispatch_routes(app, db):
    from app import (accessible_protocols_query, accessible_protocol_or_404,
                     active_organization, can_operate_protocol, current_tenant_id,
                     permission_required, read_attachment_bytes, store_attachment_bytes,
                     tenant_query)
    from models import DespachoProtocolo, HistoricoProtocolo, Lotacao, Movimentacao, Protocolo

    def can_add_dispatch(protocolo):
        if protocolo.providencias:
            from protocol_workflow import is_closed
            return bool(current_user.tipo in ('admin', 'protocolista', 'tramitador') and
                        not is_closed(protocolo) and can_operate_protocol(protocolo))
        ultimo = max(protocolo.movimentacoes, key=lambda item: item.id or 0, default=None)
        nominal_alheio = bool(current_user.tipo == 'tramitador' and ultimo and
                              ultimo.setor_destino_id == current_user.lotacao_id and
                              ultimo.destinatario_usuario_id and ultimo.destinatario_usuario_id != current_user.id)
        return bool(current_user.is_authenticated and
                    current_user.tipo in ('admin', 'protocolista', 'tramitador') and
                    not protocolo.arquivado_em and protocolo.status != 'ARQUIVADO' and
                    not protocolo.aguardando_recebimento_inicial and
                    can_operate_protocol(protocolo) and not nominal_alheio and
                    not tenant_query(Movimentacao).filter_by(
                        protocolo_id=protocolo.id, recebido_em=None).first())

    @app.context_processor
    def dispatch_context():
        return {'can_add_dispatch': can_add_dispatch, 'dispatch_body': dispatch_body}

    @app.get('/protocolo/<int:protocolo_id>/despachos/novo')
    @permission_required('route')
    def novo_despacho(protocolo_id):
        import secrets
        protocolo = accessible_protocol_or_404(protocolo_id)
        if not can_add_dispatch(protocolo):
            abort(403)
        return render_template('despacho_editor.html', protocolo=protocolo,
                               assunto='', texto='', conteudo_delta='',
                               envio_token=secrets.token_urlsafe(24), falha=False)

    @app.post('/protocolo/<int:protocolo_id>/despachos')
    @permission_required('route')
    def adicionar_despacho(protocolo_id):
        protocolo = accessible_protocols_query().filter(
            Protocolo.id == protocolo_id).with_for_update().first_or_404()
        if not can_add_dispatch(protocolo):
            abort(409 if protocolo.arquivado_em or protocolo.status == 'ARQUIVADO' or
                  protocolo.aguardando_recebimento_inicial or
                  tenant_query(Movimentacao).filter_by(protocolo_id=protocolo.id, recebido_em=None).first()
                  else 403)
        assunto = (request.form.get('assunto') or '').strip()
        if not assunto or len(assunto) > 250 or any(ord(ch) < 32 for ch in assunto):
            abort(400, description='Informe o assunto, com até 250 caracteres.')
        conteudo_delta = (request.form.get('conteudo_delta') or '').strip()
        texto = (request.form.get('texto') or '').replace('\r\n', '\n').replace('\r', '\n').strip()
        if conteudo_delta:
            try:
                conteudo_delta, texto = normalize_delta(conteudo_delta)
            except ValueError as exc:
                abort(400, description=str(exc))
        token = request.form.get('envio_token') or ''
        if not texto or len(texto) > MAX_DISPATCH_LENGTH or '\x00' in texto:
            abort(400, description='Informe o despacho, com até 100.000 caracteres.')
        if not re.fullmatch(r'[A-Za-z0-9_-]{20,80}', token):
            abort(400, description='Reabra o protocolo e tente novamente.')
        if tenant_query(DespachoProtocolo).filter_by(protocolo_id=protocolo.id, envio_token=token).first():
            flash('Este despacho já foi registrado.', 'info')
            return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id, _anchor='despachos'))

        numero = (tenant_query(DespachoProtocolo).filter_by(protocolo_id=protocolo.id)
                  .with_entities(func.max(DespachoProtocolo.numero)).scalar() or 0) + 1
        setor = tenant_query(Lotacao).filter_by(id=current_user.lotacao_id).first() if current_user.lotacao_id else None
        despacho = DespachoProtocolo(
            tenant_id=current_tenant_id(), protocolo_id=protocolo.id, numero=numero,
            protocolo_numero=protocolo.numero, texto=texto, assunto=assunto,
            conteudo_delta=conteudo_delta or None,
            autor_id=current_user.id, autor_nome=current_user.nome_completo or current_user.nome,
            autor_setor=setor.nome if setor else None,
            criado_em=datetime.now(timezone.utc), envio_token=token,
            file_name=secure_filename(f'despacho-{protocolo.numero}-{numero}.pdf'))
        try:
            data = render_dispatch_pdf(despacho, active_organization())
            path, backend, digest, stored = store_attachment_bytes(
                data, current_tenant_id(), protocolo.id, f'despacho-{token}', 1,
                despacho.file_name, 'application/pdf')
            despacho.storage_path, despacho.storage_backend = path, backend
            despacho.file_hash, despacho.file_data = digest, stored
            db.session.add(despacho)
            db.session.add(HistoricoProtocolo(
                tenant_id=current_tenant_id(), protocolo_id=protocolo.id,
                status=protocolo.status, responsavel=current_user.login,
                usuario_id=current_user.id, acao='DESPACHO_REGISTRADO',
                observacao=f'Despacho nº {numero} registrado.'))
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception('Falha ao registrar despacho no protocolo %s.', protocolo.id)
            # Não perde o texto se o armazenamento ou a geração do PDF falhar.
            return render_template('despacho_editor.html', protocolo=protocolo,
                                   texto=texto, assunto=assunto, conteudo_delta=conteudo_delta,
                                   envio_token=token, falha=True), 503
        flash('Despacho registrado.', 'success')
        return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id, _anchor='despachos'))

    @app.get('/protocolo/<int:protocolo_id>/despachos/<int:despacho_id>/pdf')
    @permission_required('view')
    def baixar_despacho(protocolo_id, despacho_id):
        accessible_protocol_or_404(protocolo_id)
        despacho = tenant_query(DespachoProtocolo).filter_by(
            id=despacho_id, protocolo_id=protocolo_id, excluido_em=None).first_or_404()
        try:
            data = read_attachment_bytes(despacho)
        except Exception:
            current_app.logger.exception('Falha ao recuperar despacho %s.', despacho.id)
            abort(503, description='O despacho está temporariamente indisponível.')
        response = send_file(io.BytesIO(data), mimetype='application/pdf',
                             as_attachment=True, download_name=despacho.file_name)
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.post('/protocolo/<int:protocolo_id>/despachos/<int:despacho_id>/excluir')
    @permission_required('delete')
    def excluir_despacho(protocolo_id, despacho_id):
        # Mesmo bloqueio da inclusão: preserva a numeração e serializa operações.
        protocolo = accessible_protocols_query().filter(
            Protocolo.id == protocolo_id).with_for_update().first_or_404()
        despacho = tenant_query(DespachoProtocolo).filter_by(
            id=despacho_id, protocolo_id=protocolo.id, excluido_em=None).first_or_404()
        motivo = (request.form.get('motivo') or '').strip()
        if request.form.get('confirmar_exclusao') != '1' or len(motivo) > 2000 or '\x00' in motivo:
            abort(400, description='Confirme a exclusão do despacho. O motivo pode ter até 2.000 caracteres.')
        despacho.excluido_em = datetime.now(timezone.utc)
        despacho.excluido_por_id = current_user.id
        despacho.motivo_exclusao = motivo or None
        db.session.add(HistoricoProtocolo(
            tenant_id=current_tenant_id(), protocolo_id=protocolo.id,
            status=protocolo.status, responsavel=current_user.login,
            usuario_id=current_user.id, acao='DESPACHO_EXCLUIDO',
            observacao=f'Despacho nº {despacho.numero} excluído.' + (f' Motivo: {motivo}' if motivo else '')))
        db.session.commit()
        flash('Despacho excluído. Registro preservado para auditoria.', 'success')
        return redirect(url_for('detalhe_protocolo', protocolo_id=protocolo.id, _anchor='despachos'))
