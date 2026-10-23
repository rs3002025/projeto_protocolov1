"""Custódia por participação, com eventos no histórico único do protocolo."""
from datetime import datetime, timezone
from functools import wraps
import re

from flask import abort, flash, redirect, request, url_for
from flask_login import current_user
from sqlalchemy import exists, func, or_, select
from werkzeug.exceptions import HTTPException

from models import (db, Protocolo, Movimentacao, ProvidenciaProtocolo,
                    AcompanhamentoProtocolo, HistoricoProtocolo, Usuario, Lotacao,
                    SolicitacaoComplemento)


def is_closed(protocol):
    return bool(protocol.excluido_em or protocol.arquivado_em or protocol.status in ('ARQUIVADO', 'FINALIZADO', 'CONCLUÍDO'))


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def workflow_feedback(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except HTTPException as error:
            if error.code not in (400, 403, 409):
                raise
            db.session.rollback()
            from flask import render_template
            message = error.description if error.code == 409 else (
                'Confira os dados informados e tente novamente.' if error.code == 400 else
                'Esta ação não está disponível para seu usuário ou para esta participação.')
            return render_template('workflow_notice.html', title='Não foi possível concluir', message=message), error.code
    return wrapped


def can_receive(movement):
    return bool(not movement.recebido_em and (current_user.tipo == 'admin' or (
        current_user.lotacao_id == movement.setor_destino_id and
        (not movement.destinatario_usuario_id or movement.destinatario_usuario_id == current_user.id))))


def can_work(participation):
    movement = participation.movimento_atual
    return bool(not participation.concluida_em and movement and movement.recebido_em and (
        current_user.tipo in ('admin', 'protocolista') or movement.recebido_por_id == current_user.id))


def my_protocol_condition():
    latest = select(func.max(Movimentacao.id)).where(
        Movimentacao.providencia_id == ProvidenciaProtocolo.id).correlate(ProvidenciaProtocolo).scalar_subquery()
    owned = exists().where(
        ProvidenciaProtocolo.protocolo_id == Protocolo.id,
        ProvidenciaProtocolo.tenant_id == Protocolo.tenant_id,
        ProvidenciaProtocolo.concluida_em.is_(None),
        Movimentacao.providencia_id == ProvidenciaProtocolo.id,
        Movimentacao.id == latest,
        or_(Movimentacao.recebido_por_id == current_user.id,
            (Movimentacao.recebido_em.is_(None) & (Movimentacao.destinatario_usuario_id == current_user.id))))
    followed = exists().where(AcompanhamentoProtocolo.protocolo_id == Protocolo.id,
                              AcompanhamentoProtocolo.usuario_id == current_user.id)
    return or_(owned, followed,
               (~Protocolo.providencias.any() & (Protocolo.responsavel == current_user.login)))


def event(protocol, action, note):
    db.session.add(HistoricoProtocolo(tenant_id=protocol.tenant_id, protocolo_id=protocol.id,
        status=protocol.status, responsavel=current_user.login, usuario_id=current_user.id,
        acao=action, observacao=note))


def locked_protocol(protocol_id):
    from app import accessible_protocols_query
    return accessible_protocols_query().filter(Protocolo.id == protocol_id).with_for_update().first_or_404()


def return_to(protocol):
    return redirect(url_for('detalhe_protocolo', protocolo_id=protocol.id))


def synchronize(protocol):
    """Campos legados só representam custódia única, nunca o último de vários donos."""
    open_items = [p for p in protocol.providencias if not p.concluida_em]
    protocol.responsavel = None
    protocol.setor_atual_id = None
    if len(open_items) == 1:
        movement = open_items[0].movimento_atual
        if movement and movement.recebido_em:
            protocol.responsavel = movement.recebido_por.login
            protocol.setor_atual_id = movement.setor_destino_id
    # Receber não significa iniciar análise. Preserve a situação de trabalho
    # explicitamente registrada mesmo quando outra participação é recebida/concluída.
    if protocol.complemento_pendente:
        protocol.status = 'PENDENTE DE DOCUMENTO'
    elif protocol.status not in ('EM ANÁLISE', 'PENDENTE DE DOCUMENTO'):
        protocol.status = 'EM TRAMITAÇÃO' if any(
            p.movimento_atual and not p.movimento_atual.recebido_em for p in open_items) else 'RECEBIDO'


@workflow_feedback
def forward_protocol(protocolo_id):
    from app import tenant_query, can_operate_protocol
    protocol = locked_protocol(protocolo_id)
    if is_closed(protocol) or protocol.aguardando_recebimento_inicial:
        abort(409, description='O processo não está disponível para encaminhamento.')
    token = request.form.get('envio_token')
    if token:
        if not re.fullmatch(r'[A-Za-z0-9_-]{20,100}', token):
            abort(400)
        if tenant_query(Movimentacao).filter_by(protocolo_id=protocol.id, enviado_por_id=current_user.id, envio_token=token).first():
            flash('Este encaminhamento já foi registrado.', 'info')
            return return_to(protocol)
    note = (request.form.get('observacao') or '').strip()
    if len(note) > 10000 or '\x00' in note:
        abort(400)
    participation = None
    raw_id = request.form.get('providencia_id')
    if raw_id:
        participation = tenant_query(ProvidenciaProtocolo).filter_by(
            protocolo_id=protocol.id, id=request.form.get('providencia_id', type=int)).first_or_404()
        if not can_work(participation):
            abort(403)
    elif protocol.providencias:
        # Iniciar novas participações é intervenção explícita do gestor do fluxo.
        if current_user.tipo not in ('admin', 'protocolista') or request.form.get('nova_providencia') != '1':
            abort(409, description='Selecione a participação que deseja encaminhar.')
    elif not can_operate_protocol(protocol):
        abort(403)
    if not protocol.providencias and tenant_query(Movimentacao).filter_by(
            protocolo_id=protocol.id, recebido_em=None).first():
        abort(409, description='Receba o encaminhamento pendente antes de continuar.')

    # A lista nominal é opcional; o formulário comum de setor/pessoa permanece válido.
    recipients = request.form.getlist('destinatarios_ids')
    if len(recipients) > 50 or len(recipients) != len(set(recipients)):
        abort(400, description='Informe até 50 destinatários distintos.')
    targets = []
    if recipients:
        if any(not value.isdecimal() for value in recipients):
            abort(400)
        if len(set(map(int, recipients))) != len(recipients):
            abort(400)
        for value in recipients:
            user = tenant_query(Usuario).filter_by(id=int(value), status='ativo').filter(
                Usuario.tipo.in_(['admin', 'protocolista', 'tramitador']),
                Usuario.lotacao_id.is_not(None)).first_or_404()
            sector = tenant_query(Lotacao).filter_by(id=user.lotacao_id, ativo=True).first_or_404()
            targets.append((sector, user))
    else:
        sector = tenant_query(Lotacao).filter_by(id=request.form.get('setor_destino_id', type=int), ativo=True).first_or_404()
        raw_user = request.form.get('destinatario_usuario_id')
        user = None
        if raw_user:
            user = tenant_query(Usuario).filter_by(id=request.form.get('destinatario_usuario_id', type=int),
                status='ativo', lotacao_id=sector.id).filter(
                Usuario.tipo.in_(['admin', 'protocolista', 'tramitador'])).first_or_404()
        targets.append((sector, user))
    # Valide todos os alvos antes de qualquer mutação: o envio é atômico.
    origin = participation.movimento_atual.setor_destino_id if participation else protocol.setor_atual_id
    previous_holder = participation.movimento_atual.recebido_por if participation else None
    for index, (sector, user) in enumerate(targets):
        item = participation if index == 0 and participation else ProvidenciaProtocolo(
            tenant_id=protocol.tenant_id, protocolo=protocol)
        db.session.add(item)
        movement = Movimentacao(tenant_id=protocol.tenant_id, protocolo_id=protocol.id,
            providencia=item, setor_origem_id=origin, setor_destino_id=sector.id,
            destinatario_usuario_id=user.id if user else None, enviado_por_id=current_user.id, observacao=note, envio_token=token)
        db.session.add(movement)
        protocol.status = 'PENDENTE DE DOCUMENTO' if protocol.complemento_pendente else 'EM TRAMITAÇÃO'
        target = f', aos cuidados de {user.nome_completo or user.nome}' if user else ', disponível a todos do setor'
        holder = f' Responsabilidade transferida de {previous_holder.nome_completo or previous_holder.nome}.' if previous_holder and index == 0 else ''
        event(protocol, 'TRAMITACAO', f'Encaminhado para {sector.nome}{target}. {holder} {note}'.strip())
    db.session.flush()
    synchronize(protocol)
    db.session.commit()
    flash('Encaminhamento registrado. Cada destinatário receberá sua participação.', 'success')
    return return_to(protocol)


@workflow_feedback
def receive_protocol(protocolo_id):
    from app import tenant_query
    protocol = locked_protocol(protocolo_id)
    if is_closed(protocol):
        abort(409)
    candidates = tenant_query(Movimentacao).filter_by(protocolo_id=protocol.id, recebido_em=None).all()
    movement_id = request.form.get('movimentacao_id', type=int)
    if movement_id:
        candidates = [m for m in candidates if m.id == movement_id]
    else:
        candidates = [m for m in candidates if can_receive(m)]
    if len(candidates) != 1:
        abort(409, description='Selecione um encaminhamento pendente para receber.')
    movement = candidates[0]
    if not can_receive(movement):
        abort(403)
    if movement.providencia and (movement.providencia.concluida_em or movement.providencia.movimento_atual.id != movement.id):
        abort(409)
    movement.recebido_por_id = current_user.id
    movement.recebido_em = utc_now()
    db.session.flush()
    if protocol.providencias:
        synchronize(protocol)
    else:
        protocol.setor_atual_id = movement.setor_destino_id
        protocol.responsavel = current_user.login
        protocol.status = 'PENDENTE DE DOCUMENTO' if protocol.complemento_pendente else 'RECEBIDO'
    target = f' (destinatário: {movement.destinatario_usuario.nome})' if movement.destinatario_usuario else ''
    event(protocol, 'RECEBIMENTO', f'Recebido por {current_user.nome_completo or current_user.nome}, setor {movement.setor_destino.nome}{target}.')
    db.session.commit()
    flash('Recebimento registrado.', 'success')
    return return_to(protocol)


def register_workflow_routes(app):
    from app import permission_required, tenant_query

    @app.post('/protocolo/<int:protocol_id>/providencia/<int:participation_id>/concluir')
    @permission_required('route')
    @workflow_feedback
    def concluir_providencia(protocol_id, participation_id):
        protocol = locked_protocol(protocol_id)
        item = tenant_query(ProvidenciaProtocolo).filter_by(id=participation_id, protocolo_id=protocol.id).first_or_404()
        if is_closed(protocol):
            abort(409)
        if not can_work(item):
            abort(403)
        result = (request.form.get('resultado') or '').strip()
        if len(result) > 10000 or '\x00' in result:
            abort(400)
        item.concluida_em, item.concluida_por_id, item.resultado = utc_now(), current_user.id, result
        synchronize(protocol)
        owner = item.movimento_atual.recebido_por
        event(protocol, 'PROVIDENCIA_CONCLUIDA', f'Providência de {owner.nome_completo or owner.nome} concluída por {current_user.nome_completo or current_user.nome}. {result}'.strip())
        db.session.commit()
        flash('Providência concluída. Concluir o processo é uma ação separada do administrador.', 'success')
        return return_to(protocol)

    @app.post('/protocolo/<int:protocol_id>/acompanhar')
    @permission_required('edit')
    def acompanhar_protocolo(protocol_id):
        protocol = locked_protocol(protocol_id)
        if current_user.tipo not in ('admin', 'protocolista'):
            abort(403)
        value = request.form.get('acompanhar')
        if value not in ('0', '1'):
            abort(400)
        record = tenant_query(AcompanhamentoProtocolo).filter_by(protocolo_id=protocol.id, usuario_id=current_user.id).first()
        if value == '1' and not record:
            db.session.add(AcompanhamentoProtocolo(tenant_id=protocol.tenant_id, protocolo_id=protocol.id, usuario_id=current_user.id))
        elif value == '0' and record:
            db.session.delete(record)
        db.session.commit()
        flash('Acompanhamento ativado.' if value == '1' else 'Acompanhamento removido.', 'success')
        return return_to(protocol)

    @app.post('/protocolo/<int:protocol_id>/finalizar')
    @permission_required('delete')
    @workflow_feedback
    def finalizar_protocolo(protocol_id):
        protocol = locked_protocol(protocol_id)
        if protocol.status in ('FINALIZADO', 'CONCLUÍDO'):
            return return_to(protocol)
        if is_closed(protocol) or protocol.aguardando_recebimento_inicial or protocol.retificacao_pendente:
            abort(409, description='Regularize o processo antes de concluir.')
        if protocol.status == 'PENDENTE DE DOCUMENTO':
            abort(409, description='Regularize a pendência de documentos antes de concluir o processo.')
        if any(not p.concluida_em for p in protocol.providencias) or tenant_query(Movimentacao).filter_by(
                protocolo_id=protocol.id, recebido_em=None).first() or tenant_query(SolicitacaoComplemento).filter_by(
                protocolo_id=protocol.id, status='PENDENTE').first():
            abort(409, description='Conclua as providências, os recebimentos e os complementos pendentes antes de concluir o processo.')
        result = (request.form.get('resultado') or '').strip()
        if len(result) > 10000 or '\x00' in result:
            abort(400)
        protocol.status, protocol.finalizado_em, protocol.resultado_final = 'CONCLUÍDO', utc_now(), result
        event(protocol, 'FINALIZACAO', result or 'Processo concluído pelo administrador.')
        db.session.commit()
        flash('Processo concluído.', 'success')
        return return_to(protocol)
