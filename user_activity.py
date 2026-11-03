"""Atividade recente, compartilhada entre réplicas e visível apenas à plataforma."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import func

ACTIVE_WINDOW = timedelta(minutes=5)
WRITE_INTERVAL = timedelta(seconds=60)


def utcnow():
    return datetime.now(timezone.utc)


def record_activity(user_id, tenant_id, now=None):
    # Transação independente: nunca confirma alterações da operação do usuário.
    # Uma linha por usuário limita o volume; escritas limitadas a uma por minuto.
    from app import db
    from models import AtividadeUsuario
    now = now or utcnow()
    table = AtividadeUsuario.__table__
    if db.engine.dialect.name == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    statement = insert(table).values(
        usuario_id=user_id, tenant_id=tenant_id, ultimo_acesso_em=now)
    statement = statement.on_conflict_do_update(
        index_elements=[table.c.usuario_id],
        set_={'tenant_id': tenant_id, 'ultimo_acesso_em': now},
        where=table.c.ultimo_acesso_em <= now - WRITE_INTERVAL)
    with db.engine.begin() as connection:
        connection.execute(statement)


def active_counts(now=None):
    from app import db
    from models import AtividadeUsuario, Usuario
    now = now or utcnow()
    rows = db.session.query(AtividadeUsuario.tenant_id, func.count(Usuario.id)).join(
        Usuario, Usuario.id == AtividadeUsuario.usuario_id).filter(
        Usuario.status == 'ativo', Usuario.is_platform_admin.is_(False),
        Usuario.tenant_id == AtividadeUsuario.tenant_id,
        AtividadeUsuario.ultimo_acesso_em >= now - ACTIVE_WINDOW,
        AtividadeUsuario.ultimo_acesso_em <= now).group_by(AtividadeUsuario.tenant_id).all()
    return dict(rows)


def is_recent(value, now=None):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    now = now or utcnow()
    return now - ACTIVE_WINDOW <= value <= now
