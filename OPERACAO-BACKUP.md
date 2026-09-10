# Backup e recuperação do Sysprot+

O banco PostgreSQL concentra protocolos, histórico, usuários, configurações e
logos. Os anexos novos ficam no bucket privado. A exportação Excel é um relatório
e não substitui o backup integral dos dois componentes.

## Backup

Defina `DATABASE_URL` e `BACKUP_DIRECTORY` e execute:

```sh
python scripts/database_backup.py backup --retention-days 30
python scripts/bucket_backup.py backup --retention-days 30
```

No Windows, se as ferramentas não estiverem no `PATH`, defina também
`POSTGRES_BIN` com a pasta `bin` da instalação do PostgreSQL.

O diretório precisa ser persistente e externo ao filesystem efêmero do serviço
web. Cada execução produz um dump PostgreSQL e um arquivo `.sha256`. O comando
só publica o arquivo depois que `pg_restore --list` confirma que o dump pode ser
lido. A retenção remove apenas dumps `sysprot-*.dump` antigos dentro do diretório
explicitamente configurado.

Cada execução do bucket produz um `.zip`, um `.zip.sha256` e um manifesto interno
com chave, tamanho e SHA-256 de cada objeto. Nenhuma credencial é incluída.

## Restauração de teste

Crie um banco PostgreSQL vazio, defina `RESTORE_DATABASE_URL` apontando para ele
e execute, substituindo o nome abaixo pelo arquivo escolhido:

```sh
python scripts/database_backup.py restore /backups/sysprot-AAAAMMDDTHHMMSSZ.dump \
  --confirm RESTAURAR:sysprot-AAAAMMDDTHHMMSSZ.dump

python scripts/bucket_backup.py restore /backups/sysprot-bucket-AAAAMMDDTHHMMSSZ.zip \
  --confirm RESTAURAR:sysprot-bucket-AAAAMMDDTHHMMSSZ.zip
```

As ferramentas validam os checksums e recusam banco ou bucket de destino que não
estejam vazios. Após restaurar, deve-se iniciar uma instância de homologação,
acessar `/health` e testar login, consulta pública, anexos e PDF.

## O que ainda depende da infraestrutura

O script não agenda sua própria execução nem transforma o disco do serviço web
em armazenamento durável. É necessário configurar um job agendado e um volume
ou cofre externo, com criptografia, acesso restrito e cópia em local distinto do
banco principal. A rotina só pode ser considerada homologada depois de uma
restauração real e documentada.

