"""One public completion status, with read compatibility for historical values."""
COMPLETED_STATUSES = ('CONCLUÍDO', 'FINALIZADO')
INITIAL_RECEIPT_ACTIONS = ('RECEBIMENTO_PORTAL', 'RECEBIMENTO_AUTOMATICO')
MANUAL_STATUSES = ('EM ANÁLISE', 'PENDENTE DE DOCUMENTO')
PROTOCOL_STATUSES = ('PROTOCOLO GERADO', 'AGUARDANDO RECEBIMENTO', 'RECEBIDO', 'EM ANÁLISE', 'PENDENTE DE DOCUMENTO',
                     'CONCLUÍDO', 'EM TRAMITAÇÃO', 'ARQUIVADO')


def canonical_status(status):
    return 'CONCLUÍDO' if status in COMPLETED_STATUSES else status


def filter_status(query, column, status):
    if status in COMPLETED_STATUSES:
        return query.filter(column.in_(COMPLETED_STATUSES))
    return query.filter(column == status)


def grouped_status_counts(rows):
    totals = {}
    for row in rows:
        key = canonical_status(row.status)
        totals[key] = totals.get(key, 0) + row.total
    return [{'status': key, 'total': count} for key, count in sorted(totals.items())]
