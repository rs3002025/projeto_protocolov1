"""Filas operacionais do painel: consultas de leitura, sem ampliar permissões."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import abort, url_for
from flask_login import current_user
from sqlalchemy import and_, case, exists, false, func, or_, select, union_all
from sqlalchemy.orm import selectinload, joinedload

from models import (Protocolo, ProvidenciaProtocolo, Movimentacao,
                    AcompanhamentoProtocolo, SolicitacaoComplemento, HistoricoProtocolo)
from protocol_status import canonical_status


def today_brasilia():
    return datetime.now(ZoneInfo('America/Sao_Paulo')).date()


def current_locations(tenant_id):
    """Uma linha por processo/setor atual, inclusive destinos paralelos pendentes."""
    latest = select(func.max(Movimentacao.id)).where(
        Movimentacao.tenant_id == tenant_id,
        Movimentacao.providencia_id == ProvidenciaProtocolo.id
    ).correlate(ProvidenciaProtocolo).scalar_subquery()
    participating = select(ProvidenciaProtocolo.protocolo_id.label('protocolo_id'),
                           Movimentacao.setor_destino_id.label('setor_id')).join(
        Movimentacao, Movimentacao.providencia_id == ProvidenciaProtocolo.id).where(
            ProvidenciaProtocolo.tenant_id == tenant_id, Movimentacao.tenant_id == tenant_id,
            ProvidenciaProtocolo.concluida_em.is_(None), Movimentacao.id == latest).distinct()
    legacy = select(Protocolo.id.label('protocolo_id'), Protocolo.setor_atual_id.label('setor_id')).where(
        Protocolo.tenant_id == tenant_id,
        ~Protocolo.providencias.any(ProvidenciaProtocolo.concluida_em.is_(None)))
    return union_all(participating, legacy).subquery('localizacoes_painel')


def build_workbench(args):
    from app import (accessible_protocols_query, current_tenant_id, tenant_query,
                     pendencias_recebimento_query, pendencias_recebimento_inicial_query)

    today = today_brasilia()
    manager = current_user.tipo in ('admin', 'protocolista')
    can_route = manager or current_user.tipo == 'tramitador'
    scope = args.get('escopo') or ('equipe' if manager or not can_route else 'meu')
    if scope not in ('meu', 'equipe'):
        abort(400, description='Visão do painel inválida.')
    if scope == 'equipe' and not manager and can_route:
        abort(403)
    queue = args.get('fila') or 'prioridades'
    page = args.get('pagina', '1')
    if not str(page).isdecimal() or not 1 <= int(page) <= 100000:
        abort(400, description='Página inválida.')

    latest = select(func.max(Movimentacao.id)).where(
        Movimentacao.tenant_id == current_tenant_id(),
        Movimentacao.providencia_id == ProvidenciaProtocolo.id
    ).correlate(ProvidenciaProtocolo).scalar_subquery()
    owned = exists().where(
        ProvidenciaProtocolo.tenant_id == current_tenant_id(),
        ProvidenciaProtocolo.protocolo_id == Protocolo.id,
        ProvidenciaProtocolo.concluida_em.is_(None),
        Movimentacao.providencia_id == ProvidenciaProtocolo.id,
        Movimentacao.id == latest,
        Movimentacao.recebido_por_id == current_user.id,
        Movimentacao.recebido_em.is_not(None))
    mine = or_(owned, and_(~Protocolo.providencias.any(), Protocolo.responsavel == current_user.login))
    watching = exists().where(
        AcompanhamentoProtocolo.tenant_id == current_tenant_id(),
        AcompanhamentoProtocolo.protocolo_id == Protocolo.id,
        AcompanhamentoProtocolo.usuario_id == current_user.id)
    receipt = false()
    personal_receipt = false()
    if can_route:
        movements = pendencias_recebimento_query()
        personal_movements = movements.filter(or_(
            Movimentacao.destinatario_usuario_id == current_user.id,
            and_(Movimentacao.destinatario_usuario_id.is_(None),
                 Movimentacao.setor_destino_id == current_user.lotacao_id)
        )) if current_user.lotacao_id else movements.filter(Movimentacao.destinatario_usuario_id == current_user.id)
        personal_receipt = Protocolo.id.in_(personal_movements.with_entities(Movimentacao.protocolo_id).statement)
        receipt = or_(
            Protocolo.id.in_(movements.with_entities(Movimentacao.protocolo_id).statement),
            Protocolo.id.in_(pendencias_recebimento_inicial_query().with_entities(Protocolo.id).statement))

    base = accessible_protocols_query().filter(
        Protocolo.arquivado_em.is_(None),
        or_(Protocolo.status.is_(None), ~Protocolo.status.in_(['FINALIZADO', 'CONCLUÍDO', 'ARQUIVADO'])))
    sector_legacy = and_(~Protocolo.providencias.any(),
        Protocolo.setor_atual_id == current_user.lotacao_id,
        ~Protocolo.movimentacoes.any(Movimentacao.recebido_em.is_(None))) if can_route and current_user.lotacao_id else false()
    work = base.filter(or_(mine, personal_receipt, sector_legacy)) if scope == 'meu' else base
    if scope == 'meu':
        receipt = personal_receipt
    overdue = Protocolo.prazo_em < today
    soon = and_(Protocolo.prazo_em >= today, Protocolo.prazo_em <= today + timedelta(days=7))
    documents = or_(Protocolo.status == 'PENDENTE DE DOCUMENTO', Protocolo.solicitacoes_complemento.any(
        SolicitacaoComplemento.status == 'PENDENTE'))
    queues = {
        'prioridades': ('Todos em aberto', work),
        'receber': ('Para receber', work.filter(receipt)),
        'comigo': ('Sob minha responsabilidade', base.filter(mine)),
        'analisar': ('Recebidos para análise', work.filter(Protocolo.status == 'RECEBIDO', ~documents)),
        'documentos': ('Aguardando documentos', work.filter(documents)),
        'acompanhar': ('Em acompanhamento', base.filter(watching)),
        'atrasados': ('Prazos vencidos', work.filter(overdue)),
        'prazos': ('Próximos 7 dias', work.filter(soon)),
        'sem_prazo': ('Sem prazo definido', work.filter(Protocolo.prazo_em.is_(None))),
    }
    if current_user.tipo == 'admin':
        queues['concluir'] = ('Aguardando conclusão', work.filter(Protocolo.status == 'AGUARDANDO CONCLUSÃO'))
    if queue not in queues or (queue == 'receber' and not can_route):
        abort(400, description='Fila do painel inválida.')
    counts = {key: query.count() for key, (_, query) in queues.items()}
    tab_keys = ['prioridades'] + (['receber', 'analisar', 'comigo'] if can_route else []) + ['documentos']
    if current_user.tipo in ('admin', 'protocolista'):
        tab_keys.append('acompanhar')
    if current_user.tipo == 'admin':
        tab_keys.append('concluir')
    queue_url = lambda key, **extra: url_for('home', escopo=scope, fila=key, **extra) + '#fila-de-trabalho'
    short_labels = {'prioridades':'Em aberto','receber':'Para receber','analisar':'Para analisar','comigo':'Comigo',
                    'documentos':'Documentos','acompanhar':'Acompanhando','concluir':'Conclusão'}
    tabs = [{'key': key, 'label': short_labels[key], 'count': counts[key], 'url': queue_url(key)} for key in tab_keys]
    selected = queues[queue][1]
    selected = selected.order_by(
        case((overdue, 0), (receipt, 1), (soon, 2), (Protocolo.status == 'RECEBIDO', 3), (documents, 4), else_=5),
        Protocolo.prazo_em.asc().nullslast(), Protocolo.data_solicitacao.asc().nullslast(), Protocolo.id.asc())
    selected = selected.options(
        joinedload(Protocolo.setor_atual),
        selectinload(Protocolo.providencias).selectinload(ProvidenciaProtocolo.movimentos).joinedload(Movimentacao.setor_destino))
    pagination = selected.paginate(page=int(page), per_page=8, error_out=False)
    visible_ids = [p.id for p in pagination.items]
    receiving_ids = {p.id for p in base.filter(receipt, Protocolo.id.in_(visible_ids)).with_entities(Protocolo.id).all()} if visible_ids and can_route else set()
    legacy_ids = [p.id for p in pagination.items if not p.providencias]
    last_legacy = {}
    if legacy_ids:
        latest_ids = select(func.max(Movimentacao.id)).where(
            Movimentacao.tenant_id == current_tenant_id(), Movimentacao.protocolo_id.in_(legacy_ids)
        ).group_by(Movimentacao.protocolo_id)
        last_legacy = {m.protocolo_id: m for m in tenant_query(Movimentacao).filter(
            Movimentacao.id.in_(latest_ids)).options(joinedload(Movimentacao.setor_destino)).all()}
    rows = []
    for protocol in pagination.items:
        days = (protocol.prazo_em - today).days if protocol.prazo_em else None
        due_label = ('Sem prazo definido' if days is None else 'Vence hoje' if days == 0 else
                     f"Vencido há {abs(days)} {'dia' if days == -1 else 'dias'}" if days < 0 else f"Vence em {days} {'dia' if days == 1 else 'dias'}")
        action, anchor = 'Ver processo', ''
        if protocol.id in receiving_ids:
            action, anchor = 'Conferir recebimento', '#tramitacao'
        elif can_route:
            action = 'Continuar atendimento'
            anchor = '#tramitacao'
        if protocol.providencias:
            destinations = [p.movimento_atual for p in protocol.providencias if not p.concluida_em and p.movimento_atual]
            location = '; '.join(dict.fromkeys(m.setor_destino.nome + (' (aguardando recebimento)' if not m.recebido_em else '') for m in destinations)) or 'Atendimentos encerrados'
        else:
            movement = last_legacy.get(protocol.id)
            location = (movement.setor_destino.nome + ' (aguardando recebimento)' if movement and not movement.recebido_em else
                        protocol.setor_atual.nome if protocol.setor_atual else
                        'Equipe de protocolo' if protocol.modalidade_abertura == 'remota_requerente' else 'Setor não informado')
        rows.append({'protocol': protocol, 'due_label': due_label, 'location':location,
                     'urgency': 'late' if days is not None and days < 0 else 'soon' if days is not None and days <= 7 else '',
                     'action': action, 'url': url_for('detalhe_protocolo', protocolo_id=protocol.id) + anchor})
    deadlines = work.filter(soon).order_by(Protocolo.prazo_em, Protocolo.id).limit(4).all()
    status_rows = work.with_entities(Protocolo.status, func.count(Protocolo.id)).group_by(Protocolo.status).all()
    grouped = {}
    for status, count in status_rows:
        label = canonical_status(status) or 'PROTOCOLO GERADO'
        grouped[label] = grouped.get(label, 0) + count
    distribution = [{'label': label.title(), 'count': count,
                     'percent': round(100 * count / max(1, counts['prioridades']))}
                    for label, count in sorted(grouped.items(), key=lambda item: -item[1])]
    cards = [
        {'label': 'Em aberto', 'count': counts['prioridades'], 'key':'prioridades', 'tone':'teal', 'hint':'Total de processos nesta visão'},
        {'label': 'Para receber', 'count': counts['receber'], 'key':'receber', 'tone':'blue', 'hint':'Entradas e encaminhamentos atuais'},
        {'label': 'Prazos vencidos', 'count': counts['atrasados'], 'key':'atrasados', 'tone':'red', 'hint':'Somente processos ainda abertos'},
        {'label': 'Aguardando documentos', 'count': counts['documentos'], 'key':'documentos', 'tone':'amber', 'hint':'Pendências de informação ou anexo'},
    ]
    if not can_route:
        cards = [card for card in cards if card['key'] != 'receber']
    for card in cards:
        card['url'] = queue_url(card['key'])
    if counts['receber'] and can_route:
        focus = {'title': 'Comece pelos recebimentos', 'text': f"Aguardando conferência de recebimento nesta visão: {counts['receber']}.", 'url':queue_url('receber'), 'action':'Ver recebimentos'}
    elif counts['atrasados']:
        focus = {'title':'Os prazos merecem atenção', 'text': f"Processos em aberto com prazo vencido: {counts['atrasados']}.", 'url':queue_url('atrasados'), 'action':'Conferir prazos'}
    elif counts['analisar'] and can_route:
        focus = {'title':'Há pedidos prontos para conferência', 'text': f"Recebidos e aguardando o início da análise: {counts['analisar']}.", 'url':queue_url('analisar'), 'action':'Ver pedidos recebidos'}
    else:
        focus = {'title':'Seu próximo passo está aqui', 'text':'Consulte a fila, acompanhe os prazos e continue de onde parou.', 'url':queue_url('prioridades'), 'action':'Ir para a fila'}
    activity_scope = accessible_protocols_query()
    if scope == 'meu':
        activity_scope = activity_scope.filter(or_(mine, personal_receipt, watching, sector_legacy))
    activity = tenant_query(HistoricoProtocolo).filter(
        HistoricoProtocolo.protocolo_id.in_(activity_scope.with_entities(Protocolo.id).statement),
        HistoricoProtocolo.acao.in_(['CRIACAO','TRAMITACAO','RECEBIMENTO','DESPACHO_REGISTRADO',
                                  'COMPLEMENTO_SOLICITADO','COMPLEMENTO_ENVIADO','FINALIZACAO'])
    ).options(joinedload(HistoricoProtocolo.protocolo)).order_by(
        HistoricoProtocolo.data_movimentacao.desc(), HistoricoProtocolo.id.desc()).limit(4).all()
    return dict(today=today, manager=manager, can_route=can_route, scope=scope, queue=queue,
                queue_title=queues[queue][0], tabs=tabs, counts=counts, cards=cards, focus=focus,
                rows=rows, pagination=pagination, deadlines=deadlines, distribution=distribution, activity=activity,
                next_url=queue_url(queue,pagina=pagination.next_num) if pagination.has_next else None,
                previous_url=queue_url(queue,pagina=pagination.prev_num) if pagination.has_prev else None,
                soon_url=queue_url('prazos'), undated_url=queue_url('sem_prazo'),
                name=(current_user.nome or current_user.login or 'Usuário').split()[0])
