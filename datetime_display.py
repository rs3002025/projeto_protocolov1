"""Horários de apresentação; não altera timestamps ou evidências persistidos."""
from datetime import timezone
from zoneinfo import ZoneInfo

def format_brasilia(value, fmt='%d/%m/%Y %H:%M'):
    if value is None:
        return ''
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo('America/Sao_Paulo')).strftime(fmt)
