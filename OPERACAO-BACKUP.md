# Backup e recuperação do Sysprot+

O banco PostgreSQL concentra protocolos, histórico, usuários, configurações,
logos e o conteúdo binário dos anexos. A exportação Excel é um relatório e não
substitui o backup integral.

## Backup

Defina `DATABASE_URL` e `BACKUP_DIRECTORY` e execute:

```sh
python scripts/database_backup.py backup --retention-days 30
```

O diretório precisa ser persistente e externo ao filesystem efêmero do serviço
web. Cada execução produz um dump PostgreSQL e um arquivo `.sha256`. O comando
só publica o arquivo depois que `pg_restore --list` confirma que o dump pode ser
lido. A retenção remove apenas dumps `sysprot-*.dump` antigos dentro do diretório
explicitamente configurado.

## Restauração de teste

Crie um banco PostgreSQL vazio, defina `RESTORE_DATABASE_URL` apontando para ele
e execute, substituindo o nome abaixo pelo arquivo escolhido:

```sh
python scripts/database_backup.py restore /backups/sysprot-AAAAMMDDTHHMMSSZ.dump \
  --confirm RESTAURAR:sysprot-AAAAMMDDTHHMMSSZ.dump
```

A ferramenta valida o checksum e o catálogo do dump e recusa bancos que já
tenham tabelas no esquema `public`. Após restaurar, deve-se iniciar uma instância
de homologação, acessar `/health` e testar login, consulta pública, anexos e PDF.

## O que ainda depende da infraestrutura

O script não agenda sua própria execução nem transforma o disco do serviço web
em armazenamento durável. É necessário configurar um job agendado e um volume
ou cofre externo, com criptografia, acesso restrito e cópia em local distinto do
banco principal. A rotina só pode ser considerada homologada depois de uma
restauração real e documentada.
