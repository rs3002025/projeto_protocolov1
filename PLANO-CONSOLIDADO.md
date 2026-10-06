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
2. Concluir o certificado de *.visual.muniprot.com.br: Railway informa validação pela autoridade certificadora. DNS e domínios já configurados; não contornar a verificação HTTPS.
3. Homologar a rotina nativa de restauração e confirmar cópia independente dos anexos do bucket. PITR está desligado em produção; ativação não é pressuposto para afirmar que os snapshots funcionam.
4. Decidir e implementar a etapa de perguntas aleatórias do autocadastro originalmente prevista; o formulário atual usa verificações fixas. Recuperação de acesso remoto ainda é mediada pelo administrador.
5. Atualizar manuais e slides com cadastro atual, PIN e subdomínios; repetir homologação visual de portal, celular, PDF longo e versões.
6. Conferir versões das dependências instaladas e vulnerabilidades conhecidas, com registro do resultado.
7. Ampliar auditoria das demais operações administrativas conforme a necessidade de rastreabilidade; o acesso do administrador geral agora está contemplado.

## Decisões mantidas

- WebAuthn, níveis adicionais e ICP-Brasil não são tarefas pendentes deste escopo.
- Portal do servidor e sistema administrativo têm entradas separadas; não existe uma página de escolha de área.
- Cliente é identificado pelo subdomínio; cliente.muniprot.com.br/portaldoservidor é a entrada do servidor.
- Desenvolvimento principal e visual possuem seus próprios bancos e configurações. Igualdade de código não significa igualdade de dados ou recursos.
- O plano geral antigo dizia que não havia bloqueadores; essa afirmação antecede as funções posteriores e não vale como aceite atual.

## Critérios para encerrar o próximo ciclo

Testes de regressão aprovados; publicação confirmada nos três ambientes; teste completo com dois clientes e perfis distintos; cadastro e e-mail reais; emissão e retificação com download de todas as versões; PDF multipágina conferido visualmente; backup/restauração documentados; materiais de treinamento correspondentes à versão publicada. Não declarar ausência absoluta de vulnerabilidades.

