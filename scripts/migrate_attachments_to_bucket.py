"""Migra anexos legados do PostgreSQL para o bucket privado.

Execute primeiro sem --apply para obter apenas a contagem. A migração preserva
metadados e versões, confere o SHA-256 após a leitura do objeto e só então remove
o binário da linha do banco.
"""
import argparse
import hashlib
import os

from app import app, bucket_client, db, store_attachment_bytes
from models import Anexo


def migrate(apply=False):
    with app.app_context():
        anexos = Anexo.query.filter(
            Anexo.storage_backend == 'database', Anexo.file_data.isnot(None)).order_by(Anexo.id).all()
        print(f'{len(anexos)} anexo(s) legado(s) encontrado(s).')
        if not apply:
            return
        client = bucket_client()
        if not client:
            raise RuntimeError('As variáveis do Railway Bucket não estão configuradas.')
        for anexo in anexos:
            data = anexo.file_data
            path, backend, digest, _ = store_attachment_bytes(
                data, anexo.tenant_id, anexo.protocolo_id, anexo.documento_chave,
                anexo.versao, anexo.file_name, anexo.mime_type)
            response = client.get_object(Bucket=os.environ['AWS_S3_BUCKET_NAME'], Key=path)
            if hashlib.sha256(response['Body'].read()).hexdigest() != digest:
                raise RuntimeError(f'Falha na verificação do anexo {anexo.id}.')
            anexo.storage_path = path
            anexo.storage_backend = backend
            anexo.file_hash = digest
            anexo.file_data = None
            db.session.commit()
            print(f'Anexo {anexo.id} migrado e verificado.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    migrate(parser.parse_args().apply)
