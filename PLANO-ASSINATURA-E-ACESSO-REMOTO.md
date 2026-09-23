# Plano de autenticação eletrônica do protocolo e abertura remota — Sysprot

## 1. Objetivo

O Sysprot terá dois recursos relacionados, mas distintos:

1. **Autenticação eletrônica pelo protocolista:** permitir que o protocolista gere e imprima o protocolo/requerimento sem precisar assiná-lo manualmente. O documento registrará eletronicamente qual usuário autenticado realizou a emissão.
2. **Abertura remota pelo requerente:** permitir que o servidor abra de casa um protocolo em seu próprio login. O acesso individual e o envio registrado já constituem evidência inicial de autoria do pedido.

Não será criado um módulo genérico para assinatura de vários documentos. O único documento envolvido é o requerimento/protocolo gerado pelo próprio sistema.

O Sysprot é privado e multiempresa. Ele oferece o mecanismo técnico; cada cliente decide se habilita a emissão eletronicamente autenticada e a abertura remota.

As duas funcionalidades serão independentes e desativadas por padrão:

- `emissao_eletronica_protocolista_enabled`;
- `portal_servidor_remoto_enabled`.

Somente o administrador geral da plataforma poderá ativá-las ou desativá-las para cada cliente, de acordo com a contratação e a decisão formal do cliente. O administrador do cliente poderá consultar o estado e administrar usuários autorizados, mas não habilitar recurso que não esteja liberado para sua organização.

## 2. Os dois atos registrados

### 2.1 Ato do protocolista

No atendimento presencial ou no lançamento administrativo, o protocolista:

- identifica o requerente;
- registra o pedido;
- confere os dados;
- gera o número do protocolo;
- emite ou imprime o requerimento/comprovante.

Nesse momento, o sistema registrará que o documento foi emitido eletronicamente pelo protocolista autenticado. Isso substituirá a assinatura manuscrita do responsável pelo protocolo.

O selo não deverá afirmar que o requerente assinou eletronicamente. Ele deverá afirmar algo como:

> Protocolo emitido e autenticado eletronicamente no Sysprot por NOME DO PROTOCOLISTA, matrícula ***123, em 23/09/2026 às 10:30.

### 2.2 Ato do requerente remoto

Quando o próprio servidor entra em sua conta e envia o pedido de casa, o sistema registrará:

- identidade da conta;
- vínculo com o cadastro funcional;
- data e hora do envio;
- conteúdo submetido;
- anexos apresentados;
- sessão utilizada.

O documento poderá informar:

> Requerimento enviado eletronicamente no Sysprot pelo próprio requerente autenticado, NOME, matrícula ***123, em 23/09/2026 às 10:30.

Esse fluxo não depende de um protocolista preencher o requerimento. O sistema poderá gerar automaticamente o número e o comprovante ou encaminhar o pedido para conferência, conforme configuração do cliente.

## 3. Situações possíveis

### Atendimento pelo protocolista

- requerente: pessoa indicada no formulário;
- usuário criador: protocolista;
- autenticador da emissão: protocolista;
- evidência produzida: documento oficialmente emitido pelo sistema;
- não afirmar que o protocolista manifestou vontade em nome do requerente.

### Abertura pelo próprio requerente

- requerente: servidor vinculado à conta;
- usuário criador: o próprio requerente;
- evidência produzida: pedido submetido pela conta individual;
- emissão do documento: automática pelo sistema;
- eventual conferência posterior do protocolista não altera quem apresentou o pedido.

### Lançamento administrativo por administrador

- requerente, usuário criador e responsável pela emissão permanecem separados;
- o documento indica corretamente quem realizou o lançamento;
- o administrador não aparece como requerente nem como protocolista, salvo se possuir também essa atribuição.

## 4. Referência do Sys Ofícios

Repositório analisado: `rs3002025/sistema-oficios`, branch `main`, em 23/09/2026.

### Componentes aproveitáveis

- confirmação de senha;
- validação com `bcrypt`;
- registro de usuário e data;
- código de conferência;
- selo no PDF;
- página pública de validação;
- SHA-256 do PDF;
- auditoria e isolamento por cliente.

### Correções necessárias no Sysprot

- O código do Sys Ofícios é um hash truncado de alguns campos, não do documento completo.
- O PDF pode ser regenerado e o hash de auditoria sobrescrito.
- A página pública confirma o código, mas não necessariamente o arquivo apresentado.
- A expressão “assinado digitalmente” não descreve com precisão a confirmação interna utilizada.
- Não há uma separação explícita entre autoria do pedido e responsabilidade pela emissão.

No Sysprot, o selo identificará exatamente o ato praticado: **pedido enviado pelo requerente** ou **protocolo emitido pelo protocolista**.

## 5. Identidades e responsabilidades

O protocolo deverá registrar separadamente:

- `requerente_servidor_id` ou dados do requerente;
- `criado_por_usuario_id`;
- `emitido_por_usuario_id`;
- modalidade de abertura: `presencial_protocolista`, `remota_requerente` ou `administrativa`;
- data do envio do pedido;
- data da emissão do protocolo;
- canal de abertura;
- organização e setor.

Uma mesma pessoa poderá ocupar mais de um papel, mas cada papel continuará registrado separadamente.

## 6. Autenticação do protocolista

Para eliminar a assinatura manual, a emissão deverá exigir:

- usuário individual ativo;
- perfil com permissão de protocolista;
- organização e setor definidos;
- sessão autenticada e não expirada;
- confirmação explícita da emissão;
- nova confirmação da senha para a emissão autenticada, ao menos quando a sessão for antiga ou a política do cliente exigir;
- registro de data, sessão e usuário;
- trilha de auditoria.

O segundo fator pode ser exigido no login ou na emissão conforme a política do cliente. Não é necessário solicitar senha e segundo fator a cada simples impressão de uma cópia já autenticada. A autenticação acontece na emissão original; reimpressões ficam registradas como cópias do mesmo documento.

## 7. Acesso e envio pelo requerente de casa

A conta do requerente deverá estar vinculada previamente ao cadastro funcional do mesmo cliente:

- usuário;
- servidor;
- CPF e matrícula;
- cargo e lotação;
- situação ativa;
- `tenant_id`.

O login individual já é uma evidência de autoria. Para fortalecê-la, o plano prevê:

- senha forte;
- segundo fator configurável;
- controle de tentativas;
- expiração e gerenciamento de sessões;
- registro de dispositivo e eventos de segurança;
- bloqueio após desligamento ou inativação;
- declaração de confirmação antes do envio.

O sistema não exigirá assinatura manuscrita do requerente remoto. A autenticação decorrerá do conjunto formado por conta vinculada, sessão, confirmação, conteúdo congelado e auditoria.

## 8. Geração do documento definitivo

Depois da confirmação do protocolista ou do envio remoto:

1. reservar o número do protocolo;
2. gerar o PDF definitivo;
3. registrar os papéis das pessoas envolvidas;
4. calcular SHA-256 dos anexos;
5. relacionar os anexos no requerimento;
6. armazenar o PDF no bucket;
7. calcular SHA-256 completo do PDF final;
8. criar token público aleatório;
9. gravar a evidência de emissão/envio;
10. impedir alteração silenciosa do documento e dos anexos.

Uma falha no banco ou no bucket não poderá deixar o protocolo parcialmente autenticado.

## 9. Hash, selo e QR Code

O SHA-256 completo não ficará na lateral do documento. Ele possui 64 caracteres e serve melhor como evidência técnica armazenada no banco e apresentada na consulta.

O PDF terá um bloco discreto no rodapé ou ao final do requerimento, contendo:

- descrição exata do ato;
- nome e matrícula parcialmente protegida de quem praticou o ato;
- data e hora;
- código curto aleatório;
- QR Code;
- endereço de validação.

Exemplo presencial:

> Protocolo emitido e autenticado eletronicamente por JOÃO DA SILVA, protocolista, matrícula ***123, em 23/09/2026 às 10:30. Código: A7B9-X2P4.

Exemplo remoto:

> Requerimento enviado eletronicamente pelo próprio requerente autenticado, MARIA DE SOUZA, matrícula ***456, em 23/09/2026 às 09:15. Código: C4D8-K7M2.

O QR Code apontará para um token não sequencial. Não conterá CPF, matrícula completa, ID interno ou dados da sessão.

O hash do arquivo final será calculado depois da geração. Não se tentará imprimir dentro do PDF o hash dos próprios bytes finais, pois a inclusão alteraria o arquivo e, consequentemente, seu hash.

## 10. Reimpressão, retificação e cancelamento

### Reimpressão

- utiliza exatamente o PDF original armazenado;
- não gera novo hash nem nova autenticação;
- registra usuário, data e motivo da reimpressão, quando solicitado;
- pode receber indicação visual de “segunda via”, sem modificar o original armazenado.

### Retificação

- preserva o requerimento original;
- gera novo documento e novo hash;
- cria relação entre original e retificação;
- informa essa situação na consulta pública.

### Cancelamento

- não apaga o documento;
- registra responsável, data e motivo;
- altera a situação na página de conferência;
- mantém o histórico para auditoria.

## 11. Anexos

Os anexos não receberão assinatura individual, mas serão vinculados ao pedido:

- armazenamento no bucket;
- SHA-256 de cada arquivo;
- nome, tamanho, MIME e hash registrados;
- impossibilidade de substituição após a emissão;
- validação de extensão, MIME real e tamanho.

O comprovante poderá listar os anexos que integravam o pedido na data do protocolo.

## 12. Verificação pública

A consulta por código ou QR Code mostrará, conforme configuração do cliente:

- validade e situação;
- organização;
- número do protocolo;
- modalidade de abertura;
- ato registrado: envio do requerente ou emissão do protocolista;
- responsável pelo ato, com dados proporcionais;
- data e hora;
- existência de retificação ou cancelamento;
- SHA-256 completo.

Poderá haver envio de PDF para comparação do hash. O arquivo será descartado após o cálculo. A rota terá limitação de tentativas e não permitirá enumerar protocolos ou clientes.

## 13. Etapas de implementação

### Progresso em 23/09/2026 — ambiente visual

Concluído neste bloco:

- campos que separam criador, servidor requerente, emissor e modalidade de abertura;
- emissão eletrônica opcional, liberada por cliente e restrita a administrador/protocolista;
- confirmação da senha individual do emissor;
- registro de evidência com identidade congelada, método, data/hora, hashes da origem e do navegador, código e token públicos;
- geração única do PDF definitivo e armazenamento no mesmo bucket privado dos documentos;
- SHA-256 integral e imutável do PDF;
- reimpressão do mesmo arquivo armazenado, sem regeneração ou substituição do hash;
- congelamento de dados e anexos após a emissão;
- selo que declara corretamente a autenticação da emissão pelo protocolista;
- QR Code de validação e página pública com comparação opcional do arquivo;
- teste automatizado que altera o arquivo e confirma a reprovação de integridade;
- níveis forte e externo identificados como ainda indisponíveis na interface.

Pendente:

- fluxo formal de retificação e cancelamento;
- vinculação administrável entre conta e cadastro de servidor;
- Portal do Servidor e sessão própria;
- envio remoto em nome próprio;
- encadeamento dos eventos críticos de auditoria;
- homologação visual e operacional no Railway.

### Etapa 1 — Papéis e dados

- separar requerente, criador e emissor;
- criar modalidades de abertura;
- ajustar permissões do protocolista;
- vincular contas remotas a servidores;
- adicionar configurações por cliente.

### Etapa 2 — Emissão autenticada do protocolista

- criar confirmação da emissão;
- registrar evidência do protocolista;
- gerar selo correto no PDF;
- eliminar a linha de assinatura manual do responsável;
- salvar PDF definitivo;
- permitir reimpressão do mesmo arquivo.

### Etapa 3 — Abertura remota

- criar “Novo protocolo em meu nome”;
- preencher identidade pelo vínculo funcional;
- registrar declaração e envio;
- implementar controles de sessão e segundo fator;
- gerar comprovante automaticamente.

### Etapa 4 — Integridade e conferência

- armazenar PDF e anexos no bucket;
- calcular hashes imutáveis;
- criar token, QR Code e consulta;
- implementar comparação do arquivo;
- criar retificação e cancelamento.

### Etapa 5 — Homologação

- testar atendimento presencial completo;
- imprimir documento sem assinatura manual;
- testar reimpressão;
- abrir pedido de casa em computador e celular;
- testar adulteração, retificação e cancelamento;
- testar isolamento entre clientes;
- revisar PDF, consulta, manual e treinamento.

## 14. Testes obrigatórios

- somente usuário com perfil adequado autentica a emissão como protocolista;
- protocolista aparece como emissor, nunca como requerente por engano;
- requerente remoto só abre em próprio nome quando vinculado;
- usuário de outro cliente não pode ser vinculado ou utilizado;
- sessão inválida ou usuário bloqueado impedem a operação;
- alteração de um byte do PDF falha na conferência;
- anexos não podem ser substituídos;
- hash original nunca é sobrescrito;
- reimpressão entrega o mesmo arquivo;
- retificação preserva o original;
- cancelamento não apaga evidências;
- falha no banco ou bucket não deixa estado parcial;
- PDF com várias páginas mantém o selo corretamente.

## 15. Uso jurídico e terminologia

O hash isoladamente não é assinatura. A força da evidência decorre do conjunto: usuário individual, permissão, vínculo funcional, sessão, confirmação, conteúdo imutável, hash, data e auditoria.

Na primeira versão, o sistema utilizará termos precisos:

- **“protocolo emitido e autenticado eletronicamente pelo protocolista”**; ou
- **“requerimento enviado eletronicamente pelo requerente autenticado”**.

Não será utilizada a expressão “assinatura digital ICP-Brasil” sem certificado correspondente. Integrações GOV.BR, ICP-Brasil ou provedor privado poderão ser adicionadas futuramente por cliente, sem alterar o núcleo do protocolo.

## 16. Critérios de conclusão

O recurso estará concluído quando:

- o protocolista emitir e imprimir o protocolo sem assinatura manual;
- o documento identificar corretamente o protocolista responsável pela emissão;
- reimpressões conservarem o mesmo original autenticado;
- o servidor puder enviar pedido de casa em seu próprio login;
- o sistema diferenciar emissão administrativa de autoria do pedido;
- PDF e anexos estiverem protegidos por hashes imutáveis;
- QR Code e consulta confirmarem a autenticidade;
- cada cliente puder habilitar os recursos independentemente;
- testes de isolamento, integridade e fluxos presenciais/remotos estiverem aprovados.

## 17. Níveis de garantia e validade jurídica

O produto deverá produzir evidências tecnicamente auditáveis e compatíveis com os requisitos de identificação, manifestação de vontade, integridade e detecção de alterações. Entretanto, não deverá afirmar que qualquer mecanismo interno é automaticamente ICP-Brasil ou universalmente válido para todos os atos.

Cada organização terá um nível de garantia configurado pelo administrador geral:

### Nível 1 — Emissão autenticada interna

- usuário e sessão identificados;
- confirmação explícita;
- senha novamente solicitada quando necessário;
- PDF e anexos imutáveis;
- hash SHA-256;
- data, hora e auditoria.

Esse nível atende à emissão operacional do protocolo, desde que aceito pelo cliente para esse ato.

### Nível 2 — Confirmação criptográfica forte

- todos os controles do nível anterior;
- segundo fator;
- preferencialmente WebAuthn/passkey;
- desafio criptográfico vinculado ao hash do requerimento;
- armazenamento da chave pública, credencial, contador e resposta assinada;
- verificação posterior independente da confirmação.

O uso de WebAuthn permite que o ato seja confirmado por uma chave privada sob controle do usuário, sem armazenar essa chave no Sysprot. A classificação jurídica final continuará dependendo do método e da aceitação do cliente, mas as evidências serão substancialmente mais fortes do que senha e código TOTP isolados.

### Nível 3 — Provedor externo

- GOV.BR, ICP-Brasil ou provedor privado;
- credenciais e contratos pertencentes ao cliente;
- validação da resposta e do certificado;
- conservação do envelope, cadeia e evidências fornecidas pelo provedor.

O nível será definido por cliente e, futuramente, por tipo de ato. A interface sempre informará o método realmente utilizado.

### Pacote de evidências

Para cada emissão ou envio autenticado, o sistema preservará um pacote contendo:

- identidade e papel do usuário no momento do ato;
- organização e setor;
- modalidade de abertura;
- data/hora UTC e fuso apresentado;
- hash do PDF e hashes dos anexos;
- versão do formato do documento;
- declaração confirmada pelo usuário;
- método e nível de autenticação;
- identificador da sessão e da credencial, sem armazenar segredos;
- resultado da verificação criptográfica, quando existir;
- histórico de emissão, consulta, reimpressão, retificação e cancelamento;
- versão dos termos e da configuração vigente no momento do ato.

Os relógios dos serviços deverão ser sincronizados. Datas serão gravadas em UTC e apresentadas no fuso do cliente.

### Auditoria

Os registros críticos serão append-only: não poderão ser editados ou excluídos pelas telas comuns. Será utilizada encadeamento de hashes ou mecanismo equivalente para revelar remoção, alteração ou reordenação de eventos. Exportações de auditoria incluirão hash e identificação do período.

O administrador geral poderá verificar integridade e prestar suporte, mas qualquer acesso excepcional aos dados do cliente também será auditado.

## 18. Recursos opcionais por cliente

Criar uma tabela central de capacidades contratadas, separada das preferências internas da organização. Ela conterá:

- `tenant_id`;
- emissão eletrônica do protocolista habilitada;
- portal remoto habilitado;
- nível máximo de garantia liberado;
- provedores externos liberados;
- data de ativação e desativação;
- administrador geral responsável;
- referência administrativa/contratual opcional;
- motivo da alteração;
- histórico imutável de mudanças.

Regras:

- recurso desabilitado não aparece no menu nem aceita chamada direta à rota/API;
- a validação ocorre no servidor, não apenas na interface;
- desativar o recurso impede novos atos, mas não invalida nem apaga os anteriores;
- documentos já autenticados continuam verificáveis;
- ativação ou desativação gera evento de auditoria;
- os dois recursos podem ser habilitados separadamente.

## 19. Portal do Servidor para acesso de casa

A abertura remota terá ambiente próprio, denominado **Portal do Servidor**, visual e funcionalmente separado do backoffice utilizado por administradores, protocolistas e tramitadores.

### Separação recomendada

- domínio ou endereço próprio, por exemplo `servidor.sysprot.com.br/<cliente>` ou `<cliente>.servidor.sysprot.com.br`;
- layout simplificado e responsivo;
- autenticação e sessão com audiência própria;
- somente funcionalidades do requerente;
- APIs explicitamente permitidas para o portal;
- ausência dos menus administrativos, tramitação geral, clientes e relatórios internos;
- controles de segurança e limites próprios.

O portal pode compartilhar o mesmo backend, banco e bucket do núcleo do Sysprot. Não é recomendável duplicar banco ou lógica de protocolo, pois isso criaria divergências e novos riscos. A separação será de superfície, rotas, sessão, permissões e domínio, mantendo uma única fonte de dados com isolamento por `tenant_id`.

### Funcionalidades do portal

- entrar e recuperar acesso;
- concluir ativação e segundo fator;
- abrir requerimento em nome próprio;
- anexar documentos;
- acompanhar protocolos próprios;
- consultar movimentações permitidas;
- responder pendências e complementar documentos;
- baixar requerimento e comprovante;
- visualizar sessões e encerrar acessos;
- atualizar apenas dados pessoais que o cliente permitir.

O portal não permitirá criar usuários, setores, clientes, tramitar protocolos de terceiros ou acessar relatórios administrativos.

## 20. Divisão das telas de login

O usuário comum não deverá escolher uma organização em uma lista geral. Isso prejudica a experiência e revela desnecessariamente a existência de outros clientes.

### Login do backoffice

Destinado a administrador do cliente, protocolista, tramitador e consulta interna. O cliente será identificado por:

- subdomínio próprio; ou
- link com `slug` da organização; ou
- convite que já contenha a organização.

A tela exibirá a identidade visual do cliente e pedirá apenas usuário e senha. Não apresentará lista de organizações.

### Login do Portal do Servidor

Será acessado pelo endereço específico do cliente. A organização já estará resolvida antes da autenticação. A tela mostrará nome/logo do cliente, usuário ou CPF permitido e senha, seguida do segundo fator quando configurado.

### Login do administrador geral

Terá endereço separado e não dependerá de seleção de cliente. Após entrar, o administrador geral escolherá a organização somente dentro do painel administrativo e toda troca de contexto será auditada.

### Resolução e segurança

- `slug` ou subdomínio será validado antes de procurar o usuário;
- mensagens de erro não revelarão se organização ou usuário existe;
- cookies e sessões do portal, backoffice e administração geral terão nomes e escopos distintos;
- redirecionamentos não poderão mudar o usuário para outro cliente;
- convites e recuperação de senha serão vinculados a uma única organização;
- logins iguais poderão existir em clientes diferentes sem conflito;
- a aplicação rejeitará qualquer tentativa de autenticar uma conta contra `tenant_id` diferente.

## 21. Ordem de implementação revisada

1. Criar capacidades opcionais por cliente e auditoria das ativações.
2. Separar as identidades e entradas do administrador geral, backoffice e Portal do Servidor.
3. Implementar resolução automática do cliente por endereço/slug, eliminando a escolha de cliente pelo usuário comum.
4. Separar requerente, criador e emissor no protocolo.
5. Implementar emissão autenticada do protocolista e reimpressão do PDF original.
6. Criar pacote de evidências, hash imutável, QR Code e verificação.
7. Implementar vínculo entre conta e servidor.
8. Construir o Portal do Servidor e o fluxo remoto em nome próprio.
9. Adicionar WebAuthn/passkey e política de nível de garantia.
10. Homologar juridicamente o conjunto de evidências, a auditoria e os documentos gerados.
11. Executar testes de segurança, isolamento multiempresa, dispositivos móveis e fluxos completos.

