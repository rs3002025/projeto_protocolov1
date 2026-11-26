"""Focused SQL ordering regressions; no application startup or real protocol data."""
from types import SimpleNamespace

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, select

from protocol_number_ordering import protocol_number_ordering

RECORDS = [
    (1, '0001/2025'), (2, '9/2026'), (3, '10/2026'),
    (4, '1096/2026'), (5, '1096-A/2026'), (6, '1096/2026-A'),
    (7, '1096/2026-RH'), (8, '1097/2026'), (9, '1097-A/2026'),
    (10, '1098-A/2026'), (11, '1638/2026'), (12, '0002/2027'),
    (13, 'invalid'), (14, None), (15, '9999999999999999999/2026'),
    (16, '1096/2026'), (17, '0001/2026-RH'), (18, '0001-A/2026-RH'),
    (19, '1096/202A'), (20, '1/2026'), (21, '1096/2026-A-RH'),
    (22, '1096-A/2026-RH'), (23, '0001/2025-RH'),
]
EXPECTED_IDS = [12, 11, 10, 8, 9, 16, 4, 6, 5, 22, 21, 7, 3, 2, 20,
                18, 17, 1, 23, 19, 15, 14, 13]


@pytest.fixture
def fixture_db():
    engine = create_engine('sqlite://')
    metadata = MetaData()
    table = Table('fixture', metadata, Column('id', Integer, primary_key=True),
                  Column('numero', String))
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(table.insert(), [{'id':i, 'numero':n} for i,n in RECORDS])
    yield engine, table
    engine.dispose()


def ordered(table):
    model = SimpleNamespace(id=table.c.id, numero=table.c.numero)
    return select(table.c.id).order_by(*protocol_number_ordering(model, 'sqlite'))


def test_all_documentary_formats_and_numeric_sequences(fixture_db):
    engine, table = fixture_db
    with engine.connect() as connection:
        assert connection.execute(ordered(table)).scalars().all() == EXPECTED_IDS


def test_page_boundary_is_stable_and_complete(fixture_db):
    engine, table = fixture_db
    with engine.connect() as connection:
        first = connection.execute(ordered(table).limit(10)).scalars().all()
        second = connection.execute(ordered(table).offset(10).limit(10)).scalars().all()
        third = connection.execute(ordered(table).offset(20).limit(10)).scalars().all()
    assert first + second + third == EXPECTED_IDS
    assert not set(first).intersection(second)


def test_normal_numbers_before_suffix_and_equivalent_suffix_uses_id(fixture_db):
    engine, table = fixture_db
    with engine.connect() as connection:
        rows = connection.execute(ordered(table)).scalars().all()
    assert [i for i in rows if i in {4,5,6,7,16}] == [16,4,6,5,7]


def test_bad_and_oversized_numbers_fall_last_without_cast_failure(fixture_db):
    engine, table = fixture_db
    with engine.connect() as connection:
        assert connection.execute(ordered(table)).scalars().all()[-4:] == [19,15,14,13]
