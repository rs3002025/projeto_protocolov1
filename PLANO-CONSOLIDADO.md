# Plano consolidado — Muniprot / Sysprot

Atualização: 06/10/2026. Este arquivo passa a ser a referência vigente. Os planos anteriores ficam preservados como histórico; decisões substituídas não devem ser reintroduzidas como tarefas pendentes.

## Entregas existentes

- Protocolos, numeração por cliente, tramitação por setor/usuário, recebimento, prazos, relatórios e arquivamento.
- Administrador geral, administrador de cliente, protocolista, tramitador e consulta; portal limitado ao requerente.
- Logomarcas por cliente, melhorias de layout, navegação e PDFs multipágina.
- Portal do servidor com importação de cadastro funcional, confirmação de dados e e-mail; suporte restrito à equipe interna.
- Emissão eletrônica por PIN pessoal de seis números, documento preservado com hash, consulta pública e validação em QR distintos; retificações mantêm número e versões anteriores.
- Anexos de até 5 MB por arquivo em bucket; conferência de hash na recuperação.
- E-mail transacional e domínios por cliente; áreas administrativa e portal com entradas próprias.
- Backup manual de banco e bucket com teste histórico de restauração; produção com snapshots nativos diários, semanais e mensais confirmados em 06/10.
- Manuais e apresentações em português, incluindo materiais para equipe do cliente.

## Correções implementadas neste bloco

- Retificação bloqueada em processo arquivado e quando a capacidade de emissão está desabilitada.
- Novos eventos de auditoria incluem a data do histórico no conteúdo protegido; eventos antigos continuam conferidos em seu formato original.
- Exportação Excel preserva campos textuais como texto, evitando fórmulas vindas do conteúdo do protocolo.
- Limitação de login e evidências de origem passam a usar o endereço normalizado pelo proxy configurado.
- Seleção de cliente pelo administrador geral registrada no histórico auditável do cliente.
- DOCX/XLSX precisam de estrutura Office válida, sem macros, criptografia ou expansão excessiva.
- Alteração de senha invalida sessões e cookies de acesso anteriores; a sessão que realizou a alteração é renovada. A primeira publicação desta mudança exige novo login nas sessões antigas.
- Mensagem de limite alinhada: 5 MB por anexo; 30 MB de requisição total, incluindo o formulário.
- Destino nominal não concede consulta automaticamente aos colegas do setor; participantes anteriores mantêm consulta legitimamente obtida no fluxo.

Validação: 60 testes aprovados na execução conjunta e o teste de logo aprovado separadamente após completar as imagens de preparação do snapshot; 61 verificações aprovadas no total. Os testes usam banco temporário. As correções foram integradas às três branches; a consolidação final mantém a mesma versão de código em main, development e codex/visual-development. A implantação é automática no Railway e precisa ser conferida no painel.

Endereços: produção em app.muniprot.com.br e cliente.muniprot.com.br; desenvolvimento principal em dev.muniprot.com.br e cliente.dev.muniprot.com.br; visual em visual.muniprot.com.br e cliente.visual.muniprot.com.br. O wildcard visual segue aguardando emissão do certificado. Bancos, buckets e variáveis continuam específicos de cada ambiente.

## Pendências vigentes

1. Homologar no navegador a restrição de destinatário nominal e a preservação do acesso de participantes anteriores, já implementadas neste bloco.
2. Concluído em 07/10/2026: certificado de *.visual.muniprot.com.br emitido após reinício da emissão pelo Railway. HTTPS em prefeitura.visual.muniprot.com.br confirmado sem advertência; chamado marcado Solved pelo usuário via assistência. Nenhuma alteração adicional de DNS necessária.
3. Homologar a rotina nativa de restauração e confirmar cópia independente dos anexos do bucket. PITR está desligado em produção; ativação não é pressuposto para afirmar que os snapshots funcionam.
4. Perguntas aleatórias implementadas: matrícula primeiro, uma pergunta sobre o nome da mãe e uma sobre a data de nascimento, identificação válida por 15 minutos e vinculada ao cliente. Os 65 testes automatizados passaram, incluindo bloqueio de envio de e-mail sem identificação, resposta incorreta, expiração e tentativa entre clientes. Falta conferir visualmente a execução publicada. Recuperação de acesso remoto ainda é mediada pelo administrador.
5. Atualizar manuais e slides com cadastro atual, PIN e subdomínios; repetir homologação visual de portal, celular, PDF longo e versões.
6. Conferir versões das dependências instaladas e vulnerabilidades conhecidas, com registro do resultado. Workflow de pip-audit adicionado para cada publicação e execução manual; o relatório deve ser conferido antes de encerrar a pendência. A resolução do requirements não substitui o inventário efetivamente instalado no Railway.
7. Ampliar auditoria das demais operações administrativas conforme a necessidade de rastreabilidade; o acesso do administrador geral agora está contemplado.

## Decisões mantidas

- WebAuthn, níveis adicionais e ICP-Brasil não são tarefas pendentes deste escopo.
- Portal do servidor e sistema administrativo têm entradas separadas; não existe uma página de escolha de área.
- Cliente é identificado pelo subdomínio; cliente.muniprot.com.br/portaldoservidor é a entrada do servidor.
- Desenvolvimento principal e visual possuem seus próprios bancos e configurações. Igualdade de código não significa igualdade de dados ou recursos.
- O plano geral antigo dizia que não havia bloqueadores; essa afirmação antecede as funções posteriores e não vale como aceite atual.

## Critérios para encerrar o próximo ciclo

Testes de regressão aprovados; publicação confirmada nos três ambientes; teste completo com dois clientes e perfis distintos; cadastro e e-mail reais; emissão e retificação com download de todas as versões; PDF multipágina conferido visualmente; backup/restauração documentados; materiais de treinamento correspondentes à versão publicada. Não declarar ausência absoluta de vulnerabilidades.

## Limitações encontradas na continuação de 06/10

- *.visual.muniprot.com.br ainda apresenta ERR_CERT_COMMON_NAME_INVALID; não foi contornada a advertência do navegador.
- Credenciais locais do bucket protegidas pelo Windows não puderam ser descriptografadas no contexto desta execução. Não foram apagadas, alteradas ou expostas; a tentativa não gerou backup novo.
- A instalação local do auditor foi impedida pela restrição de rede ao PyPI; por isso a consulta foi transferida ao GitHub Actions.
- Sessão administrativa fornecida pelo usuário em produção. A homologação real encontrou falha PostgreSQL no agrupamento por setor do dashboard; corrigida pela PR 104, com teste da consulta compilada para PostgreSQL. Materiais antigos permanecem preservados; sua atualização não está concluída.

## Continuação do ciclo

### Retomada em 07/10/2026

### Correções após teste real do portal

- Campo de entrada Matrícula; navegação Meus dados; download Baixar requerimento; ato público distingue envio do servidor de confirmação do protocolista.
- CPF funcional, endereço e telefone da conta são copiados para novos requerimentos. Documentos já emitidos permanecem preservados.
- Usuários internos separados das contas do portal. Gestão de servidores paginada, por cliente, com edição funcional e ativação/desativação da conta vinculada.
- Servidor altera endereço e telefone; novo e-mail exige código de confirmação, expira em 15 minutos, cinco tentativas persistentes por código e intervalo persistente de um minuto entre envios. Dados funcionais são corrigidos pela administração.
- Envio externo fica aguardando recebimento, sem atribuir responsabilidade ao servidor. Recebimento inicial exclusivo de admin/protocolista; PIN quando emissão eletrônica habilitada; responsável e status RECEBIDO registrados na mesma transação. Status e tramitação não podem pular o recebimento.
- PDF de nova emissão conserva bloco de envio do requerente e acrescenta bloco do protocolista no espaço correspondente. Anexos não exibem hash no corpo do documento; integridade permanece registrada.
- Importador rejeita data numérica ou inválida antes de gravar e apresenta a linha; erros de banco são revertidos sem deixar sessão transacional quebrada.
- 74 testes passaram em banco temporário, incluindo contato, confirmação de e-mail, isolamento administrativo, recebimento com PIN e preservação de versões. Publicação e visualização finais precisam ser confirmadas após este registro.

Suporte do certificado encerrado em 07/10: chamado wildcard-tls-pending-for-visual-munipr-9ddd7cc7 com status Solved, confirmado no navegador. As referências históricas abaixo ao certificado pendente ficam superadas por este registro.

Publicação no GitHub: PR 105 integrada; main, development e codex/visual-development atualizadas para e98d6da191061b3eae63f959aa37a435c4effd89. Implantação no Railway e conferência visual autenticada ainda precisam ser confirmadas, não inferidas a partir das branches.

- Consulta administrativa de elegibilidade do portal implementada: pesquisa por matrícula, dados faltantes e contas já vinculadas, com isolamento por cliente e sem expor CPF, nascimento ou nome da mãe completos na listagem.
- Cadastro recusa dados funcionais vazios ou CPF fora do formato de onze dígitos. Isso é uma verificação de formato, não uma validação de identidade ou dos dígitos verificadores do CPF.
- Auditoria administrativa ampliada para usuários, setores, tipos, importação, identidade visual e geração de recuperação do portal. Registro na mesma transação da operação; senhas, PINs e tokens não são registrados.
- Regressão: 70 testes aprovados conjuntamente, em banco temporário. Conferência visual autenticada desta nova tela ainda pendente: Chrome não disponível na conexão de navegação em 07/10.
- Matrícula 1300695: pré-cadastro sem CPF, nascimento e nome da mãe; não foi liberada por exceção. Pré-cadastro fictício TESTE-20261006 criado para teste em produção, sem criar conta. A matrícula só permanece disponível para autocadastro enquanto não vinculada a uma conta.
- Ajustada a sequência de IDs de servidores em produção após detectar que estava atrás dos IDs existentes. Os registros anteriores foram preservados.
- Materiais, restauração nativa, cópia independente de anexos, certificado visual e homologação ponta a ponta continuam pendentes; os 70 testes não encerram essas tarefas.

Regressão final após correção do painel e controle de reenvio: 66 testes aprovados conjuntamente, usando banco temporário (06/10/2026).

- PR 103: cadastro em etapas e perguntas sorteadas publicado, com Deployment successful confirmado nos três ambientes e primeira tela conferida visualmente em produção. Suite completa: 65 testes passaram.
- GitHub Actions 37488148413, 06/10/2026 às 15:31 UTC: pip-audit retornou No known vulnerabilities found, com relatório preservado. Resultado limitado às versões resolvidas pelo requirements no CI; não representa auditoria integral nem inventário de cada contêiner.
- PR 104: correção do dashboard e intervalo mínimo de um minuto entre códigos de cadastro para a mesma matrícula, inclusive em outra sessão. 11 testes específicos passaram. Commit 6f01c4626daac89035b846a339d32d0f8797c6c8 nas três branches. Produção confirmou Deployment successful; painel real carregou estatísticas, gráficos e distribuição de 110 protocolos por setor. Filtro SEAD mostrou 1 protocolo; ao remover o filtro, a visão geral voltou corretamente, sem aviso. Evidência visual: tmp/dashboard-corrigido-2026-10-06.png.

