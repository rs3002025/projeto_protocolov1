"""Datas de negócio separadas das regularizações administrativas do acervo."""
from sqlalchemy import and_, case, or_, select, tuple_
from models import HistoricoProtocolo, Movimentacao, Protocolo

ESTIMATED_COMPLETION = 'CONCLUSAO_ESTIMADA_ACERVO'


def historical_marks(actions, *, regularization=False):
    query = select(HistoricoProtocolo.tenant_id, HistoricoProtocolo.protocolo_id,
                   HistoricoProtocolo.data_movimentacao).where(
        HistoricoProtocolo.protocolo_id.is_not(None),
        HistoricoProtocolo.data_movimentacao.is_not(None),
        HistoricoProtocolo.acao.in_(actions))
    if regularization:
        query = query.where(HistoricoProtocolo.responsavel == 'Regularização do acervo')
    return query


def completion_dates():
    identity = tuple_(Protocolo.tenant_id, Protocolo.id, Protocolo.finalizado_em)
    estimated = identity.in_(historical_marks([ESTIMATED_COMPLETION]))
    administrative = identity.in_(historical_marks(['FINALIZACAO'], regularization=True))
    known_date = case((or_(estimated, administrative), None), else_=Protocolo.finalizado_em)
    estimated_date = case((estimated, Protocolo.finalizado_em), else_=None)
    return known_date, estimated_date


def movement_date_precision():
    sent_day_only = tuple_(Movimentacao.tenant_id, Movimentacao.protocolo_id,
        Movimentacao.enviado_em).in_(historical_marks(['TRAMITACAO_LEGADA']))
    # Prefixos reservados pelas cargas históricas já executadas. Esses arquivos
    # registram dias, sem fornecer um horário de envio comprovado.
    sent_day_only = or_(sent_day_only, and_(
        Protocolo.modalidade_abertura == 'legado_importado', or_(
            Movimentacao.envio_token.like('acervo-%'),
            Movimentacao.envio_token.like('import-%'),
            Movimentacao.envio_token.like('importacao-%'))))
    administrative_receipt = tuple_(Movimentacao.tenant_id, Movimentacao.protocolo_id,
        Movimentacao.recebido_em).in_(historical_marks(['RECEBIMENTO'], regularization=True))
    return sent_day_only, administrative_receipt
