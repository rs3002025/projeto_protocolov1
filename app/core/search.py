from sqlalchemy import text
from ..extensions import db
from ..models import Tenant, Protocolo

def find_protocol_across_tenants(numero_completo):
    """
    Busca um protocolo em todos os schemas de tenants ativos.

    Esta é uma operação potencialmente lenta e deve ser usada com cuidado,
    principalmente para endpoints públicos.

    :param numero_completo: O número completo do protocolo (ex: "0001/2024").
    :return: Uma tupla (protocolo, tenant) se encontrado, senão (None, None).
    """
    active_tenants = Tenant.query.filter_by(is_active=True).all()

    for tenant in active_tenants:
        try:
            # Define o search_path para o schema do tenant atual
            db.session.execute(text(f'SET search_path TO "{tenant.schema_name}"'))

            protocolo = Protocolo.query.filter_by(numero=numero_completo).first()

            if protocolo:
                # Encontrou! Reseta o search_path e retorna.
                db.session.execute(text('SET search_path TO public'))
                return protocolo, tenant
        except Exception as e:
            # Se o schema não existir ou houver outro erro, loga e continua.
            print(f"Erro ao buscar no schema {tenant.schema_name}: {e}")
            db.session.rollback()
            continue

    # Se o loop terminar sem encontrar, reseta o search_path e retorna None.
    db.session.execute(text('SET search_path TO public'))
    return None, None
