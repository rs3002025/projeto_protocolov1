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
# Acesso por subdomínio

Em produção, `app.muniprot.com.br` continua sendo o domínio central da
plataforma e das consultas/validações públicas. Cada cliente pode receber
`<subdominio>.muniprot.com.br`. O administrador geral define o subdomínio em
**Administração da plataforma**; se o campo ficar em branco, utiliza-se o
identificador interno (`slug`). O usuário não precisa escolher o cliente na
tela de login. O Portal do Servidor usa `/portaldoservidor`, e a equipe usa
`/entrar`. A raiz do subdomínio leva diretamente ao login da equipe; o
Portal do Servidor tem endereço próprio, sem menu intermediário. O caminho
antigo `/portal/entrar` permanece aceito para links já distribuídos.

Os endereços antigos com o slug no caminho continuam aceitos. Ao trocar um
subdomínio, o anterior fica registrado como alias da mesma organização para
não invalidar links já distribuídos. A sessão é host-only (não configure
`SESSION_COOKIE_DOMAIN` com o domínio pai), e cada requisição compara o host,
o slug da rota e o `tenant_id` do usuário. O subdomínio identifica o cliente,
mas não substitui a autorização em cada consulta.

Para ativar: adicionar `*.muniprot.com.br` ao serviço web de **produção** no
Railway; criar todos os registros DNS de verificação, CNAME e certificado que
o Railway apresentar; aguardar o HTTPS ficar válido; então definir
`TENANT_SUBDOMAINS_ENABLED=true` e
`TENANT_BASE_DOMAIN=muniprot.com.br` no serviço de produção. Não apontar o
wildcard para os ambientes de teste. Validar os hosts `app`, cliente válido,
cliente inexistente, alias antigo e troca de host após o login. Os QR codes
de consulta e validação continuam no domínio central.


