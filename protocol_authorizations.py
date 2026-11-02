"""Autorização nominal, sem transferência de custódia do protocolo."""
import base64
import io
import json
import re
import secrets
from datetime import datetime, timezone

from flask import abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from models import db, AutorizacaoProtocolo, Anexo, HistoricoProtocolo, Lotacao, Organizacao, Protocolo, Usuario


def utc_now():
    return datetime.now(timezone.utc)


def eligible(user):
    return bool(user and user.status == 'ativo' and not user.is_platform_admin and
                user.tipo != 'requerente' and (user.tipo == 'autorizador' or user.pode_autorizar))


def enabled():
    from app import active_organization
    org = active_organization()
    return bool(org and org.autorizacao_protocolos_enabled)


def assigned(protocol):
    pending = protocol.autorizacao_pendente
    return bool(current_user.is_authenticated and enabled() and eligible(current_user) and
                pending and pending.autorizador_id == current_user.id)


def pending_for_user(user_id):
    from app import current_tenant_id
    return AutorizacaoProtocolo.query.filter_by(tenant_id=current_tenant_id(),
        autorizador_id=user_id, status='PENDENTE').first()


def dispatch_exception():
    """Permissão adicional estritamente limitada ao despacho da análise atribuída."""
    from app import tenant_query
    if request.endpoint not in {'novo_despacho', 'adicionar_despacho'}:
        return False
    pid = (request.view_args or {}).get('protocolo_id')
    protocol = tenant_query(Protocolo).filter_by(id=pid).first()
    return bool(protocol and assigned(protocol))


def request_allowed(protocol):
    from app import ROLE_PERMISSIONS, can_update_protocol_status
    from protocol_workflow import is_closed
    return bool(enabled() and 'route' in ROLE_PERMISSIONS.get(current_user.tipo, set())
                and not is_closed(protocol) and not protocol.autorizacao_pendente
                and can_update_protocol_status(protocol))


def record(protocol, action, text):
    db.session.add(HistoricoProtocolo(tenant_id=protocol.tenant_id, protocolo_id=protocol.id,
        usuario_id=current_user.id, responsavel=current_user.login, status=protocol.status,
        acao=action, observacao=text))


def render_authorization_pdf(authorization, organization):
    from weasyprint import HTML, URLFetcher
    from app import normalize_logo_png
    logo = None
    if organization.logo_data:
        data = normalize_logo_png(io.BytesIO(organization.logo_data)).getvalue()
        logo = 'data:image/png;base64,' + base64.b64encode(data).decode('ascii')
    html = render_template('autorizacao_pdf.html', autorizacao=authorization,
        resumo=json.loads(authorization.resumo), organizacao=organization, pdf_logo_url=logo)
    return HTML(string=html, url_fetcher=URLFetcher(
        allowed_protocols={'data'}, fail_on_errors=True)).write_pdf()


def register_authorization_routes(app):
    from app import (active_organization, current_tenant_id, accessible_protocols_query,
                     accessible_protocol_or_404, tenant_query, tenant_get_or_404,
                     read_attachment_bytes, store_attachment_bytes, verified_upload_mime)

    def require_feature():
        if not enabled():
            abort(404)

    def get_request(request_id, *, lock=False):
        row = tenant_query(AutorizacaoProtocolo).filter_by(id=request_id).first_or_404()
        query = accessible_protocols_query().filter(Protocolo.id == row.protocolo_id)
        protocol = (query.with_for_update() if lock else query).first_or_404()
        if lock:
            row = tenant_query(AutorizacaoProtocolo).filter_by(id=request_id).with_for_update().populate_existing().one()
            db.session.expire(protocol, ['autorizacoes'])
        if current_user.tipo == 'autorizador' and row.autorizador_id != current_user.id:
            abort(404)
        return row, protocol

    @app.before_request
    def authorization_write_guard():
        if not current_user.is_authenticated or not current_tenant_id():
            return None
        # O perfil dedicado só acessa a sua fila, os processos atribuídos e a própria conta.
        if current_user.tipo == 'autorizador':
            allowed = {'auth_list', 'auth_detail', 'auth_decide', 'auth_upload', 'auth_pdf',
                'minha_conta', 'trocar_senha_inicial', 'logout', 'static', 'organization_logo',
                'detalhe_protocolo', 'gerar_pdf_protocolo', 'baixar_anexo', 'baixar_despacho',
                'novo_despacho', 'adicionar_despacho', 'baixar_processo', 'health'}
            if request.endpoint not in allowed:
                return redirect(url_for('auth_list'))
        if request.endpoint in {'auth_request', 'auth_decide', 'auth_upload'}:
            return None  # Estas rotas bloqueiam a mesma linha antes de validar a ação.
        mutation = request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}
        edit_page = request.endpoint in {'editar_protocolo', 'retificar_protocolo', 'novo_despacho'}
        if not mutation and not edit_page:
            return None
        args = request.view_args or {}
        pid = args.get('protocolo_id') or args.get('protocol_id')
        protected_document = None
        if request.endpoint == 'atualizar_protocolo_status':
            value = (request.get_json(silent=True) or {})
            value = value.get('protocoloId') if isinstance(value, dict) else None
            if isinstance(value, (str, int)) and not isinstance(value, bool) and re.fullmatch(r'[0-9]{1,10}', str(value)):
                pid = int(value) if int(value) <= 2147483647 else None
        if request.endpoint == 'deletar_anexo':
            protected_document = tenant_query(Anexo).filter_by(id=args.get('anexo_id')).first()
            pid = protected_document.protocolo_id if protected_document else None
        if request.endpoint == 'adicionar_anexo' and (request.form.get('documento_id') or '').isdecimal():
            protected_document = tenant_query(Anexo).filter_by(id=int(request.form['documento_id']), protocolo_id=pid).first()
        if protected_document and protected_document.documento_chave.startswith('autorizacao-decisao-'):
            abort(409, description='O documento de uma decisão registrada deve ser preservado.')
        if not pid:
            return None
        protocol = accessible_protocols_query().filter_by(id=pid).with_for_update().first()
        if not protocol:
            return None  # A autorização normal da rota preserva sua resposta 403/404.
        if protocol.autorizacao_pendente:
            if request.endpoint in {'novo_despacho', 'adicionar_despacho'} and assigned(protocol):
                return None
            if request.endpoint == 'acompanhar_protocolo':
                return None
            if request.is_json:
                return {'sucesso': False, 'mensagem': 'Protocolo aguardando autorização. A operação está bloqueada.'}, 409
            return render_template('workflow_notice.html', title='Aguardando autorização',
                message='Este protocolo permanece com o responsável atual e está bloqueado até a decisão do autorizador.'), 409

    @app.context_processor
    def authorization_context():
        on = bool(current_user.is_authenticated and current_user.tipo != 'requerente' and enabled())
        people = []
        count = 0
        if on:
            people = tenant_query(Usuario).filter(Usuario.status == 'ativo', Usuario.is_platform_admin.is_(False),
                Usuario.tipo != 'requerente',
                or_(Usuario.pode_autorizar.is_(True), Usuario.tipo == 'autorizador')).order_by(Usuario.nome_completo, Usuario.nome).all()
            if eligible(current_user):
                count = tenant_query(AutorizacaoProtocolo).filter_by(autorizador_id=current_user.id, status='PENDENTE').count()
        return dict(authorization_enabled=on, authorization_assigned=assigned,
            can_request_authorization=request_allowed, authorization_people=people,
            authorization_token=secrets.token_urlsafe(24), authorization_pending_count=count,
            is_authorizer=bool(on and eligible(current_user)))

    @app.post('/protocolo/<int:protocolo_id>/solicitar-autorizacao')
    @login_required
    def auth_request(protocolo_id):
        protocol = accessible_protocols_query().filter_by(id=protocolo_id).with_for_update().first_or_404()
        # Mesmo bloqueio da administração geral: evita criar pendência durante a desativação.
        organization = Organizacao.query.filter_by(id=current_tenant_id()).with_for_update().populate_existing().one()
        if not organization.autorizacao_protocolos_enabled:
            abort(404)
        token = request.form.get('envio_token') or ''
        if not re.fullmatch(r'[A-Za-z0-9_-]{20,80}', token):
            abort(400, description='Reabra o protocolo e tente novamente.')
        previous = tenant_query(AutorizacaoProtocolo).filter_by(envio_token=token).first()
        if previous:
            if previous.protocolo_id != protocol.id or previous.solicitado_por_id != current_user.id:
                abort(409)
            return redirect(url_for('detalhe_protocolo', protocolo_id=protocol.id))
        if protocol.autorizacao_pendente:
            abort(409, description='O protocolo já aguarda autorização.')
        if not request_allowed(protocol):
            abort(403)
        value = request.form.get('autorizador_id') or ''
        if not re.fullmatch(r'[0-9]{1,10}', value) or int(value) > 2147483647:
            abort(400, description='Selecione o autorizador.')
        target = tenant_query(Usuario).filter_by(id=int(value)).first()
        if not eligible(target):
            abort(400, description='Selecione um usuário ativo com a função de autorizador neste cliente.')
        snapshot = dict(numero=protocol.numero, requerente=protocol.nome,
            tipo=protocol.tipo_requerimento, pedido=protocol.observacoes or '',
            anexos=[dict(id=a.id, nome=a.file_name, sha256=a.file_hash) for a in protocol.anexos])
        row = AutorizacaoProtocolo(tenant_id=protocol.tenant_id, protocolo_id=protocol.id,
            solicitado_por_id=current_user.id, autorizador_id=target.id, envio_token=token,
            status='PENDENTE', solicitado_em=utc_now(), resumo=json.dumps(snapshot, ensure_ascii=False))
        db.session.add(row)
        record(protocol, 'AUTORIZACAO_SOLICITADA', 'Autorização solicitada a '+(target.nome_completo or target.nome)+'. O protocolo permanece com seu responsável.')
        db.session.commit()
        flash('Autorização solicitada. O protocolo está aguardando a decisão.', 'success')
        return redirect(url_for('detalhe_protocolo', protocolo_id=protocol.id))

    @app.get('/autorizacoes')
    @login_required
    def auth_list():
        require_feature()
        if not eligible(current_user):
            abort(403)
        status = request.args.get('situacao', 'PENDENTE')
        if status not in {'PENDENTE', 'AUTORIZADO', 'NAO_AUTORIZADO', 'TODAS'}:
            abort(400)
        query = tenant_query(AutorizacaoProtocolo).filter_by(autorizador_id=current_user.id)
        if status != 'TODAS':
            query = query.filter_by(status=status)
        rows = query.order_by(AutorizacaoProtocolo.solicitado_em.desc(), AutorizacaoProtocolo.id.desc()).paginate(
            page=request.args.get('page', 1, type=int), per_page=25, error_out=False)
        return render_template('autorizacoes.html', title='Autorizações', pedidos=rows, situacao=status)

    @app.get('/autorizacoes/<int:request_id>')
    @login_required
    def auth_detail(request_id):
        require_feature()
        row, protocol = get_request(request_id)
        can_decide = bool(assigned(protocol) and row.status == 'PENDENTE' and row.autorizador_id == current_user.id)
        return render_template('autorizacao_detalhe.html', title='Autorização de protocolo',
            autorizacao=row, protocolo=protocol, resumo=json.loads(row.resumo), pode_decidir=can_decide)

    @app.post('/autorizacoes/<int:request_id>/decidir')
    @login_required
    def auth_decide(request_id):
        require_feature()
        row, protocol = get_request(request_id, lock=True)
        if not eligible(current_user) or row.autorizador_id != current_user.id:
            abort(403)
        decision = request.form.get('decisao')
        if decision not in {'AUTORIZADO', 'NAO_AUTORIZADO'}:
            abort(400)
        if row.status != 'PENDENTE':
            if row.status != decision:
                abort(409, description='A decisão já foi registrada e não pode ser sobrescrita.')
            return redirect(url_for('auth_detail', request_id=row.id))
        from protocol_workflow import is_closed
        if is_closed(protocol):
            abort(409)
        try:
            when = utc_now()
            sector = tenant_query(Lotacao).filter_by(id=current_user.lotacao_id).first() if current_user.lotacao_id else None
            # Renderização não pode descarregar um estado parcial da decisão no banco.
            with db.session.no_autoflush:
                row.status, row.decidido_em, row.decidido_por_id = decision, when, current_user.id
                row.decisor_nome = current_user.nome_completo or current_user.nome
                row.decisor_login = current_user.login
                row.decisor_setor = sector.nome if sector else None
                data = render_authorization_pdf(row, active_organization())
                filename = secure_filename(f'autorizacao-{row.id}-{protocol.numero}.pdf')
                key = f'autorizacao-decisao-{row.id}'
                path, backend, digest, stored = store_attachment_bytes(data, current_tenant_id(),
                    protocol.id, key, 1, filename, 'application/pdf')
                document = Anexo(tenant_id=protocol.tenant_id, protocolo_id=protocol.id,
                    file_name=filename, storage_path=path, storage_backend=backend, file_hash=digest,
                    file_data=stored, file_size=len(data), mime_type='application/pdf',
                    documento_chave=key, versao=1, enviado_por_id=current_user.id)
                db.session.add(document)
                row.documento = document
                record(protocol, 'AUTORIZACAO_DECIDIDA',
                    ('Protocolo autorizado' if decision == 'AUTORIZADO' else 'Protocolo não autorizado')+
                    ' por '+row.decisor_nome+'. Documento da decisão registrado. Protocolo liberado para o responsável atual.')
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception('Falha ao registrar decisão de autorização %s.', request_id)
            return render_template('workflow_notice.html', title='Decisão não registrada',
                message='Não foi possível gerar ou salvar o documento. A solicitação continua pendente e o protocolo permanece bloqueado. Tente novamente.'), 503
        flash('Decisão registrada e documento gerado. O protocolo foi liberado.', 'success')
        return redirect(url_for('auth_detail', request_id=row.id))

    @app.post('/autorizacoes/<int:request_id>/anexo')
    @login_required
    def auth_upload(request_id):
        require_feature()
        row, protocol = get_request(request_id, lock=True)
        if row.status != 'PENDENTE' or not assigned(protocol):
            abort(403)
        file = request.files.get('anexo')
        if not file:
            abort(400, description='Selecione um documento.')
        filename = secure_filename(file.filename or '')
        data = file.read(5 * 1024 * 1024 + 1)
        mime = verified_upload_mime(filename, data) if filename and data and len(data) <= 5 * 1024 * 1024 else None
        if not mime:
            abort(400, description='Envie um arquivo de tipo permitido, não vazio e de até 5 MB.')
        key = f'autorizacao-anexo-{row.id}-'+secrets.token_urlsafe(16)
        try:
            path, backend, digest, stored = store_attachment_bytes(data, current_tenant_id(), protocol.id, key, 1, filename, mime)
            db.session.add(Anexo(tenant_id=protocol.tenant_id, protocolo_id=protocol.id,
                file_name=filename, storage_path=path, storage_backend=backend, file_hash=digest,
                file_data=stored, file_size=len(data), mime_type=mime, documento_chave=key,
                versao=1, enviado_por_id=current_user.id))
            record(protocol, 'AUTORIZACAO_DOCUMENTO_ANEXADO', f'Documento {filename} anexado pelo autorizador na solicitação {row.id}.')
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception('Falha ao anexar documento na autorização %s.', row.id)
            return render_template('workflow_notice.html', title='Documento não enviado',
                message='Não foi possível salvar o documento. A solicitação continua pendente. Tente novamente.'), 503
        flash('Documento anexado ao protocolo.', 'success')
        return redirect(url_for('auth_detail', request_id=row.id))

    @app.get('/autorizacoes/<int:request_id>/documento')
    @login_required
    def auth_pdf(request_id):
        row, protocol = get_request(request_id)
        if row.status == 'PENDENTE' or not row.documento_id:
            abort(404)
        document = tenant_get_or_404(Anexo, row.documento_id)
        if document.protocolo_id != protocol.id:
            abort(404)
        try:
            data = read_attachment_bytes(document)
        except Exception:
            app.logger.exception('Falha ao recuperar documento da autorização %s.', row.id)
            abort(503)
        response = send_file(io.BytesIO(data), mimetype='application/pdf', as_attachment=True,
            download_name=document.file_name)
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response
