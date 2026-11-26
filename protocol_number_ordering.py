"""SQL ordering for documentary protocol numbers, including historical suffixes."""
from sqlalchemy import BigInteger, Integer, and_, case, cast, func, literal

# Eighteen digits fit BIGINT even at the largest allowed value. Invalid or oversized
# numbers remain sortable without evaluating an unsafe numeric conversion.
NUMBER_PATTERN = r'^[0-9]{1,18}(?:-[A-Za-z0-9]+)*/[0-9]{4}(?:-[A-Za-z0-9]+)*$'


def protocol_number_ordering(model, dialect_name):
    """Year DESC, numeric sequence DESC, normalized suffix ASC, unique ID DESC."""
    number = func.coalesce(model.numero, '')
    valid = number.regexp_match(NUMBER_PATTERN)
    position = func.instr if dialect_name == 'sqlite' else func.strpos
    slash = position(number, '/')
    hyphen = position(number, '-')
    sequence_length = case(
        (and_(hyphen > 0, hyphen < slash), hyphen - 1),
        else_=slash - 1,
    )
    year_text = func.substr(number, slash + 1, 4)
    sequence_text = func.substr(number, 1, sequence_length)
    remaining = func.substr(number, sequence_length + 1)
    suffix_text = func.replace(remaining, literal('/') + year_text, '')
    trim = func.trim if dialect_name == 'sqlite' else func.btrim
    suffix = case((valid, func.upper(trim(suffix_text, '-'))), else_='')
    year = case((valid, cast(year_text, Integer)), else_=None)
    sequence = case((valid, cast(sequence_text, BigInteger)), else_=None)
    return (
        year.desc().nulls_last(),
        sequence.desc().nulls_last(),
        suffix.asc(),
        model.id.desc(),
    )
