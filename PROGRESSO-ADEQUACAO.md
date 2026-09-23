# Plano geral consolidado — Sysprot+

## 1. Finalidade e situação atual

Este documento consolida o andamento funcional, técnico, operacional e visual do Sysprot+. Ele substitui o registro cronológico antigo, que já não representava o estado implantado.

**Situação em 22/09/2026:** o sistema possui versão homologada em produção, ambiente principal de desenvolvimento e ambiente visual isolado. O conjunto atual passou por 54 testes automatizados e por testes reais no navegador. Não há pendência funcional ou visual bloqueadora conhecida para a utilização prevista.

Ambientes oficiais:

- produção: branch `main`, em `https://sysprotocolo.up.railway.app`;
- desenvolvimento principal: branch `development`;
- desenvolvimento visual: branch `codex/visual-development`, em `https://projetoprotocolov1-visual-development.up.railway.app`.

## 2. Atendimento funcional

### 2.1 Protocolos e integridade do processo — concluído

- Numeração definida pelo servidor e separada por organização.
- Criação do protocolo e primeiro evento gravados na mesma transação.
- Estados oficiais padronizados: `PROTOCOLO GERADO`, `EM ANÁLISE`, `PENDENTE DE DOCUMENTO`, `FINALIZADO`, `CONCLUÍDO`, `EM TRAMITAÇÃO` e `ARQUIVADO`.
- Cadastro, edição, consulta, pesquisa, paginação e acompanhamento implementados.
- Histórico registra criação, alterações, tramitação, recebimento, documentos e arquivamento.
- Edição registra os campos e os valores modificados.
- Processo arquivado permanece somente para leitura.
- Arquivamento é bloqueado enquanto houver tramitação pendente.
- Revisão resumida apresentada antes da confirmação do cadastro.
- Confirmação exigida para ações sensíveis ou destrutivas.

### 2.2 Tramitação e responsabilidades — concluído

- Tramitação realizada entre setores, com envio e recebimento.
- Remetente pode indicar um usuário do setor destinatário ou deixar o destinatário individual em branco.
- Sem usuário indicado, a pendência fica disponível para os usuários aptos do setor.
- Com usuário indicado, somente o destinatário recebe a pendência individual.
- Localização, responsável e situação do recebimento aparecem no processo.
- Histórico preserva remetente, destino, destinatário, envio e recebimento.

### 2.3 Prazos, painel, relatórios e exportações — concluído

- Campo próprio de prazo utilizado nos filtros e indicadores.
- Filtros por número, requerente, tipo, status, período e situação do prazo.
- Painel apresenta novos protocolos, vencidos, próximos do vencimento, finalizados, recebimentos e suporte.
- Indicadores funcionam como atalhos para as listas correspondentes.
- Estatísticas por status, tipo e setor atual.
- Relatórios e exportação Excel protegidos por permissão.
- Filtros preservados na paginação, nos relatórios e na exportação.
- Impressão rápida, impressão personalizada e pré-visualização disponíveis.
- Fechamento dos modais validado pelo “X”, botão, clique externo e tecla Esc.

### 2.4 Documentos e anexos — concluído

- Documentos PDF usam dados institucionais do cliente.
- Cabeçalho, rodapé, logo e textos respeitam a configuração da organização.
- QR Code direciona para a consulta pública protegida.
- Documentos extensos foram testados em múltiplas páginas.
- Anexos novos ficam em bucket privado compatível com S3.
- Caminho de armazenamento inclui o identificador do cliente.
- Upload aceita arquivos diversos dentro do limite de 20 MB e rejeita arquivo vazio.
- Nova versão preserva as anteriores, com autor, data, sequência e download individual.
- Processos arquivados não recebem novos anexos.
- Exclusão permanente foi evitada para preservar a trilha documental.

### 2.5 Consulta pública — concluído

- Acesso realizado por token não sequencial apresentado no QR Code.
- Número e demais dados não são revelados antes da confirmação.
- Consulta exige a matrícula correspondente ao protocolo.
- Comparação aceita caracteres Unicode e impede consulta com matrícula incorreta.
- Limitação de tentativas reduz força bruta.
- Resposta pública expõe somente os dados definidos para acompanhamento.
- Cabeçalhos de segurança, política de conteúdo e proteção contra enquadramento estão ativos.

### 2.6 Endereço e CEP — concluído

- Consulta externa de CEP preenche logradouro, bairro e município quando disponíveis.
- Campos permanecem editáveis para correção ou preenchimento manual.
- Falha ou ausência de dados no serviço externo não impede o cadastro manual.
- CEP `62940-073` foi utilizado na validação real.

## 3. Multicliente, perfis e segurança

### 3.1 Arquitetura multicliente — concluído

- Organizações usam `tenant_id` próprio.
- Usuários, protocolos, anexos, históricos, lotações, servidores, tipos e chamados são vinculados à organização.
- Consultas autenticadas são limitadas ao cliente selecionado.
- Tentativa de acessar identificador de outro cliente retorna indisponibilidade, sem revelar o registro.
- Logos, documentos, anexos e configurações são isolados por organização.
- A suíte automatizada usa organizações distintas para verificar o isolamento.
- A demonstração visual com uma segunda organização permanece opcional, não sendo bloqueio funcional.

### 3.2 Perfis e hierarquia — concluído

- Administrador geral: gerencia a plataforma, seleciona clientes e cria outros administradores gerais.
- Administrador do cliente: gerencia sua organização, usuários do mesmo nível ou inferiores, setores, tipos e identidade.
- Protocolista: cria e acompanha protocolos, sem administrar a organização.
- Tramitador: participa da tramitação, recebimento e resposta conforme setor e destinatário.
- Consulta: acompanha os processos permitidos, sem criar, administrar ou tramitar.
- Contas inativas não autenticam.
- Administrador do cliente não atravessa organizações.
- Sistema impede desativar a própria conta ou deixar o cliente sem administrador ativo.

### 3.3 Proteções aplicadas — concluído para o escopo atual

- CSRF em formulários e requisições de alteração.
- Saída textual tratada para evitar injeção de HTML nas áreas revisadas.
- Controle de acesso aplicado nas rotas, não apenas na interface.
- Limitação de tentativas no login e na consulta pública.
- Tokens, arquivos e consultas não dependem de identificadores sequenciais públicos.
- Bucket privado; download passa pela aplicação autenticada e autorizada.
- Não existe declaração de segurança absoluta. Novas funções devem passar por revisão antes da promoção.

## 4. Identidade visual e experiência — concluído

- Logo padrão neutra Sysprot+ para contextos sem cliente definido.
- Logo de cada organização armazenada fora do código e tratada antes do uso.
- Imagens grandes são redimensionadas sem extrapolar os contêineres.
- Login resolve a identidade pelo identificador da organização informado.
- Cabeçalho, login, documentos e relatórios usam a identidade correta.
- Sistema visual, cabeçalho, navegação, botões, campos, cartões, tabelas e mensagens padronizados.
- Painel “Exige sua atenção” implementado.
- Suporte e configurações reorganizados.
- Listagens mostram filtros ativos e mantêm as ações essenciais visíveis.
- Número do protocolo é um identificador visual, sem comportamento de hiperlink.
- Responsividade validada em desktop, tablet e celular, sem rolagem horizontal indevida nas telas revisadas.
- Navegação por teclado, foco visível, rótulos e preferência por redução de movimento considerados.

O histórico detalhado está em `PLANO-EVOLUCAO-VISUAL.md`.

## 5. Suporte e capacitação — concluído

- Qualquer usuário autenticado pode abrir e acompanhar os próprios chamados.
- Chamado registra assunto, descrição, categoria, prioridade, status, responsável e atualização.
- Administradores gerais podem visualizar a fila global, assumir, responder e atualizar chamados.
- Usuário acompanha a conversa e as mudanças de situação.
- Materiais em português foram preparados para administração/desenvolvimento e para treinamento do cliente.
- A versão voltada ao cliente exclui informações internas do desenvolvedor e apresenta o uso de forma mais didática.
- Os materiais devem ser atualizados quando novas funções alterarem os fluxos apresentados.

## 6. Backup e recuperação — solução provisória homologada

- Backup PostgreSQL produz `.dump` e checksum SHA-256.
- Backup do bucket produz `.zip`, manifesto e checksum SHA-256.
- Credenciais não são gravadas dentro dos arquivos de backup.
- Restauração foi executada em banco vazio e prefixo temporário do bucket.
- Foram conferidos PostgreSQL, quantidade de protocolos e históricos, objeto restaurado e SHA-256.
- Scripts e orientação estão documentados em `OPERACAO-BACKUP.md`.
- Arquivos locais são mantidos em `C:\Users\usuario\Documents\ChatGPT\New project\Backups Sysprot`.

Situação operacional:

- a rotina local atende provisoriamente enquanto o plano atual do Railway não oferece backup nativo;
- após o upgrade do Railway, o backup nativo deverá ser ativado e testado;
- mesmo com backup nativo, recomenda-se manter cópia externa periódica e teste de restauração.

## 7. Testes e homologação

Evidências atuais:

- 54 testes automatizados aprovados;
- isolamento entre organizações coberto na suíte;
- login e permissões testados com diferentes perfis;
- criação, edição, tramitação, recebimento e arquivamento testados;
- anexos e bucket testados;
- suporte testado entre usuário e administrador geral;
- consulta pública e matrícula testadas;
- PDFs simples e multipágina homologados;
- desktop, tablet e celular revisados;
- deploy de produção conferido no navegador.

Avisos existentes de `datetime.utcnow()` são de depreciação futura do Python e não representam falha funcional atual.

## 8. Histórico de promoção

- Bloco funcional desenvolvido inicialmente em `development` e progressivamente implantado no Railway.
- Reformulação visual trabalhada em `codex/visual-development` com banco e serviços isolados.
- Promoção visual para `development`: PR nº 87.
- Promoção de `development` para `main`: PR nº 89.
- Produção atualizada e validada em 22/09/2026.

## 9. Pendências reais

Não há pendência funcional ou visual bloqueadora conhecida. Permanecem atividades de evolução e operação:

1. ativar e homologar o backup nativo do Railway após o upgrade do plano;
2. substituir gradualmente `datetime.utcnow()` por datas UTC com fuso explícito;
3. realizar periodicamente teste de restauração do banco e do bucket;
4. manter monitoramento de disponibilidade, erros, capacidade do banco e capacidade do bucket;
5. atualizar manuais e treinamento sempre que houver alteração de fluxo;
6. realizar nova revisão de segurança e permissões a cada módulo acrescentado;
7. opcionalmente demonstrar no navegador duas organizações simultâneas, embora o isolamento já esteja automatizado.

## 10. Fluxo obrigatório para os próximos ciclos

1. Registrar o objetivo e os critérios de aceite.
2. Implementar no ambiente apropriado; mudanças visuais começam em `codex/visual-development`.
3. Executar a suíte automatizada.
4. Testar o fluxo real no navegador, incluindo perfis e responsividade afetados.
5. Registrar limitações ou riscos remanescentes.
6. Obter homologação do responsável.
7. Promover para `development` e validar o deploy.
8. Promover para `main` e validar a produção.

Nenhuma alteração futura deve ser considerada concluída apenas porque o código foi enviado: o resultado implantado precisa ser conferido.

