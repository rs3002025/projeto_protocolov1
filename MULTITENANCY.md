# Arquitetura multicliente

Cada organização possui um `tenant_id`. Usuários, protocolos, anexos,
históricos, lotações, servidores e tipos de requerimento são vinculados a esse
identificador. As rotas autenticadas usam consultas limitadas à organização do
usuário; a consulta direta de um identificador pertencente a outro cliente
responde com HTTP 404.

Na primeira implantação, `bootstrap_db.py` associa os dados existentes à
organização definida por `DEFAULT_ORGANIZATION_SLUG` e
`DEFAULT_ORGANIZATION_NAME`. Os padrões são `prefeitura` e `Prefeitura`.

Para criar outro cliente no console do serviço:

```sh
ADMIN_PASSWORD='senha-temporaria-segura' python manage.py create-organization \
  --slug municipio-exemplo \
  --name 'Município Exemplo' \
  --admin-login admin \
  --admin-name 'Administrador Municipal' \
  --admin-email admin@example.gov.br
```

O campo **Organização** da tela de login recebe o `slug`.
