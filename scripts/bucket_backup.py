"""Backup e restauração do bucket S3 compatível usado pelo Sysprot+."""
import argparse
import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import xml.etree.ElementTree as ET

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


class S3Client:
    """Cliente S3 mínimo com AWS Signature V4, sem dependências externas."""

    def __init__(self, endpoint, region, access_key, secret_key):
        parsed = urllib.parse.urlsplit(endpoint.rstrip('/'))
        self.scheme, self.endpoint_host = parsed.scheme, parsed.netloc
        self.region, self.access_key, self.secret_key = region, access_key, secret_key

    @staticmethod
    def _hmac(key, value):
        import hmac
        return hmac.new(key, value.encode('utf-8'), hashlib.sha256).digest()

    def request(self, method, bucket, key='', query=None, body=b'', headers=None):
        import hmac
        now = datetime.now(timezone.utc)
        amz_date, date = now.strftime('%Y%m%dT%H%M%SZ'), now.strftime('%Y%m%d')
        host = f'{bucket}.{self.endpoint_host}'
        canonical_uri = '/' + urllib.parse.quote(key, safe='/~-._')
        pairs = sorted((str(k), str(v)) for k, v in (query or {}).items())
        canonical_query = urllib.parse.urlencode(pairs, quote_via=urllib.parse.quote, safe='~-._')
        payload_hash = hashlib.sha256(body).hexdigest()
        signed = {'host': host, 'x-amz-content-sha256': payload_hash, 'x-amz-date': amz_date}
        for name, value in (headers or {}).items():
            signed[name.lower()] = value.strip()
        signed_names = ';'.join(sorted(signed))
        canonical_headers = ''.join(f'{name}:{signed[name]}\n' for name in sorted(signed))
        canonical = '\n'.join((method, canonical_uri, canonical_query, canonical_headers,
                               signed_names, payload_hash))
        scope = f'{date}/{self.region}/s3/aws4_request'
        to_sign = '\n'.join(('AWS4-HMAC-SHA256', amz_date, scope,
                             hashlib.sha256(canonical.encode()).hexdigest()))
        key_date = self._hmac(('AWS4' + self.secret_key).encode(), date)
        key_region = self._hmac(key_date, self.region)
        key_service = self._hmac(key_region, 's3')
        signing_key = self._hmac(key_service, 'aws4_request')
        signature = hmac.new(signing_key, to_sign.encode(), hashlib.sha256).hexdigest()
        request_headers = {**(headers or {}), 'Host': host, 'x-amz-date': amz_date,
                           'x-amz-content-sha256': payload_hash,
                           'Authorization': f'AWS4-HMAC-SHA256 Credential={self.access_key}/{scope}, SignedHeaders={signed_names}, Signature={signature}'}
        url = f'{self.scheme}://{host}{canonical_uri}' + (f'?{canonical_query}' if canonical_query else '')
        with urllib.request.urlopen(urllib.request.Request(url, data=body if method == 'PUT' else None,
                                                          headers=request_headers, method=method), timeout=120) as response:
            return response.read()


def client_from_env():
    return S3Client(required_env('AWS_ENDPOINT_URL'), required_env('AWS_DEFAULT_REGION'),
                    required_env('AWS_ACCESS_KEY_ID'), required_env('AWS_SECRET_ACCESS_KEY'))


def list_keys(client, bucket):
    keys = []
    token = None
    while True:
        query = {'list-type': '2'}
        if token:
            query['continuation-token'] = token
        root = ET.fromstring(client.request('GET', bucket, query=query))
        keys.extend(node.text for node in root.findall('.//{*}Contents/{*}Key') if node.text)
        truncated = (root.findtext('.//{*}IsTruncated') or '').lower() == 'true'
        token = root.findtext('.//{*}NextContinuationToken')
        if not truncated:
            break
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
                data = client.request('GET', bucket, key=key)
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
            client.request('PUT', bucket, key=item['key'], body=archive.read(item['entry']),
                           headers={'x-amz-meta-sha256': item['sha256']})
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

