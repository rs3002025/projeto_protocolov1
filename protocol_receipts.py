"""Recebimento administrativo automático, sem atribuição de assinatura humana."""
from models import db, Organizacao, Protocolo, HistoricoProtocolo
from protocol_status import INITIAL_RECEIPT_ACTIONS


def automatic_portal_receipt(protocol, organization):
    if protocol.tenant_id != organization.id:
        raise ValueError('Organização incompatível com o protocolo.')
    if (organization.emissao_eletronica_protocolista_enabled
            or protocol.modalidade_abertura != 'remota_requerente'
            or protocol.excluido_em or protocol.arquivado_em
            or protocol.status != 'AGUARDANDO RECEBIMENTO'
            or any(h.acao in INITIAL_RECEIPT_ACTIONS for h in protocol.historico)):
        return False
    protocol.status = 'PENDENTE DE DOCUMENTO' if protocol.complemento_pendente else 'RECEBIDO'
    db.session.add(HistoricoProtocolo(tenant_id=protocol.tenant_id, protocolo_id=protocol.id, protocolo=protocol,
        status=protocol.status, usuario_id=None, responsavel='Sistema', acao='RECEBIMENTO_AUTOMATICO',
        observacao='Requerimento recebido automaticamente pelo sistema para atendimento pela equipe de protocolo.'))
    return True


def receive_pending_without_signature(organization):
    """Idempotente; serializa a mudança da regra e o recebimento por cliente."""
    organization = Organizacao.query.filter_by(id=organization.id).populate_existing().with_for_update().one()
    if organization.emissao_eletronica_protocolista_enabled:
        return 0
    pending = Protocolo.query.filter(
        Protocolo.tenant_id == organization.id,
        Protocolo.modalidade_abertura == 'remota_requerente',
        Protocolo.status == 'AGUARDANDO RECEBIMENTO',
        Protocolo.excluido_em.is_(None), Protocolo.arquivado_em.is_(None),
        ~Protocolo.historico.any(HistoricoProtocolo.acao.in_(INITIAL_RECEIPT_ACTIONS)),
    ).order_by(Protocolo.id).with_for_update().all()
    return sum(automatic_portal_receipt(protocol, organization) for protocol in pending)
