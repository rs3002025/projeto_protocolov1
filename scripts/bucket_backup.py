"""Backup e restauração do bucket S3 compatível usado pelo Sysprot+."""
import argparse
import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
import zipfile

def required_env(name):
    value = os.getenv(name, '').strip()
    if not value:
        raise SystemExit(f'A variável {name} é obrigatória.')
    return value


def safe_backup_directory(raw_path):
    directory = Path(raw_path).expanduser().resolve()
    if directory == Path(directory.anchor) or len(directory.parts) < 3:
        raise SystemExit('BACKUP_DIRECTORY deve apontar para uma pasta específica e persistente.')
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def object_entry_name(key):
    encoded = base64.urlsafe_b64encode(key.encode('utf-8')).decode('ascii').rstrip('=')
    return f'objects/{encoded}'


def client_from_env():
    import boto3
    from botocore.config import Config
    return boto3.client(
        's3', endpoint_url=required_env('AWS_ENDPOINT_URL'),
        region_name=required_env('AWS_DEFAULT_REGION'),
        aws_access_key_id=required_env('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=required_env('AWS_SECRET_ACCESS_KEY'),
        config=Config(s3={'addressing_style': os.getenv('AWS_S3_URL_STYLE', 'virtual')}),
    )


def list_keys(client, bucket):
    keys = []
    paginator = client.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket):
        keys.extend(item['Key'] for item in page.get('Contents', []))
    return sorted(keys)


def validate_archive(path):
    with zipfile.ZipFile(path, 'r') as archive:
        if archive.testzip() is not None:
            raise RuntimeError('O arquivo ZIP do bucket está corrompido.')
        manifest = json.loads(archive.read('manifest.json'))
        for item in manifest['objects']:
            data = archive.read(item['entry'])
            if len(data) != item['size'] or sha256_bytes(data) != item['sha256']:
                raise RuntimeError(f"Falha de integridade no objeto {item['key']}.")
    return manifest


def backup(retention_days):
    directory = safe_backup_directory(required_env('BACKUP_DIRECTORY'))
    bucket = required_env('AWS_S3_BUCKET_NAME')
    client = client_from_env()
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    final_path = directory / f'sysprot-bucket-{timestamp}.zip'
    temporary_path = directory / f'.{final_path.name}.tmp'
    objects = []
    try:
        with zipfile.ZipFile(temporary_path, 'w', compression=zipfile.ZIP_DEFLATED,
                             compresslevel=9) as archive:
            for key in list_keys(client, bucket):
                response = client.get_object(Bucket=bucket, Key=key)
                data = response['Body'].read()
                entry = object_entry_name(key)
                archive.writestr(entry, data)
                objects.append({'key': key, 'entry': entry, 'size': len(data),
                                'sha256': sha256_bytes(data)})
            manifest = {'format': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
                        'source_bucket': bucket, 'objects': objects}
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False,
                                                         indent=2).encode('utf-8'))
        validate_archive(temporary_path)
        temporary_path.replace(final_path)
        final_path.with_suffix('.zip.sha256').write_text(
            f'{sha256_file(final_path)}  {final_path.name}\n', encoding='ascii')
    finally:
        temporary_path.unlink(missing_ok=True)

    cutoff = datetime.now(timezone.utc).timestamp() - retention_days * 86400
    for candidate in directory.glob('sysprot-bucket-*.zip'):
        if candidate != final_path and candidate.stat().st_mtime < cutoff:
            candidate.unlink()
            candidate.with_suffix('.zip.sha256').unlink(missing_ok=True)
    print(f'{final_path} ({len(objects)} objeto(s))')


def restore(archive_file, confirmation):
    source = Path(archive_file).expanduser().resolve()
    if not source.is_file():
        raise SystemExit('Arquivo de backup do bucket não encontrado.')
    if confirmation != f'RESTAURAR:{source.name}':
        raise SystemExit(f'Confirmação inválida. Informe --confirm RESTAURAR:{source.name}')
    checksum_file = source.with_suffix('.zip.sha256')
    if not checksum_file.is_file() or checksum_file.read_text(encoding='ascii').split()[0] != sha256_file(source):
        raise SystemExit('Checksum ausente ou inválido; restauração cancelada.')
    manifest = validate_archive(source)
    bucket = required_env('AWS_S3_BUCKET_NAME')
    client = client_from_env()
    if list_keys(client, bucket):
        raise SystemExit('O bucket de destino não está vazio; restauração cancelada.')
    with zipfile.ZipFile(source, 'r') as archive:
        for item in manifest['objects']:
            client.put_object(Bucket=bucket, Key=item['key'], Body=archive.read(item['entry']),
                              Metadata={'sha256': item['sha256']})
    restored = list_keys(client, bucket)
    if restored != sorted(item['key'] for item in manifest['objects']):
        raise RuntimeError('A relação de objetos restaurados não corresponde ao manifesto.')
    print(f'Restauração do bucket concluída: {len(restored)} objeto(s).')


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command', required=True)
    backup_parser = subparsers.add_parser('backup')
    backup_parser.add_argument('--retention-days', type=int, default=30)
    restore_parser = subparsers.add_parser('restore')
    restore_parser.add_argument('archive_file')
    restore_parser.add_argument('--confirm', required=True)
    args = parser.parse_args()
    if args.command == 'backup':
        if args.retention_days < 1:
            raise SystemExit('A retenção deve ser de pelo menos um dia.')
        backup(args.retention_days)
    else:
        restore(args.archive_file, args.confirm)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Falha no backup do bucket: {error}', file=sys.stderr)
        raise SystemExit(1)

