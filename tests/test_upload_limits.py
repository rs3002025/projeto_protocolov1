import io
import pytest
from werkzeug.datastructures import FileStorage
import test_multitenancy as base
from app import app, db, validated_uploads
from models import Anexo, Protocolo

MB = 1024 * 1024


def setup_module():
    base.setup_module()


def teardown_module():
    base.teardown_module()


def upload(size):
    return FileStorage(stream=io.BytesIO(b'x' * size), filename='limite.txt')


def test_collection_accepts_20_mb_and_rejects_one_extra_byte_and_total_over_30():
    assert len(validated_uploads([upload(20 * MB)])[0][1]) == 20 * MB
    with pytest.raises(ValueError, match='20 MB'):
        validated_uploads([upload(20 * MB + 1)])
    with pytest.raises(ValueError, match='30 MB'):
        validated_uploads([upload(20 * MB), upload(11 * MB)])


def test_protocol_upload_accepts_and_replaces_20_mb_without_saving_oversized_file():
    client = app.test_client()
    base.login(client, 'cliente-a')
    with app.app_context():
        pid = Protocolo.query.filter_by(tenant_id=1).one().id
    endpoint = f'/protocolo/{pid}/anexo/novo'
    response = client.post(endpoint, data={'anexo': (io.BytesIO(b'x' * (20 * MB)), 'limite.txt')})
    assert response.status_code == 302
    with app.app_context():
        saved = Anexo.query.filter_by(protocolo_id=pid, file_name='limite.txt').one()
        identifier = saved.id
        assert saved.file_size == 20 * MB
    response = client.post(endpoint, data={'documento_id': str(identifier),
        'anexo': (io.BytesIO(b'y' * (20 * MB)), 'substituto.txt')})
    assert response.status_code == 302
    with app.app_context():
        assert Anexo.query.filter_by(protocolo_id=pid).count() == 2
    response = client.post(endpoint, data={'anexo': (io.BytesIO(b'x' * (20 * MB + 1)), 'grande.txt')})
    assert response.status_code == 302
    with app.app_context():
        assert Anexo.query.filter_by(protocolo_id=pid).count() == 2
