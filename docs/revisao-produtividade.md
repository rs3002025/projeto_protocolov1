# Produtividade e processo completo — avaliação no visual

## Entregue nesta revisão

1. Download do processo com capa, índice e marcadores navegáveis, pedido preservado, tramitação cronológica, despachos ativos e anexos atuais compatíveis. O download não cria outra versão nem altera o estado do processo.
2. Pacote ZIP com o PDF de leitura e os originais da documentação atual. Versões substituídas permanecem preservadas no sistema e não são duplicadas no pacote. Planilhas, documentos interativos, protegidos ou sem conversão têm folha de referência no PDF e permanecem íntegros no ZIP. Assinaturas digitais devem ser verificadas no original, não no PDF compilado. A autenticação eletrônica existente não é refeita.
3. Relatórios com totais de todos os resultados filtrados, filtro de setor atual que considera encaminhamentos paralelos, identificação das datas como datas do pedido e responsável apresentado conforme a tramitação. A paginação conserva filtros, inclusive o setor.
4. Apresentação simplificada dos eventos antigos de geração do requerimento e inclusão de anexos, sem nomes técnicos de versões ou chaves internas. O registro original da auditoria permanece intacto.

## Oportunidades priorizadas

| Prioridade | Melhoria | Utilidade e condição para implementação |
|---|---|---|
| Alta | Relatório de permanência por setor | Identificar onde os processos ficam parados, calculando tempo de envio e recebimento por participação. Separar espera de recebimento de tempo de atendimento. Registros importados sem hora não devem gerar precisão fictícia. |
| Alta | Tempo até conclusão e entradas versus saídas | Medir pedidos criados e conclusões efetivamente registradas por período; não confundir data do pedido com data da conclusão. Explicitar cobertura de processos antigos sem data de fechamento. |
| Alta | Pesquisas salvas por usuário | Reabrir filtros frequentes, como “meu setor / vencidos”, mantendo isolamento por cliente e sem transformar acompanhamento em atribuição. |
| Média | Alertas de prazo dentro do sistema | Avisar sobre vencimentos e recebimentos acumulados. Definir antecedência e evitar alertas repetidos; comunicações por e-mail devem ser configuradas separadamente. |
| Média | Modelos de despacho por cliente | Reutilizar estrutura e formatação, exigindo revisão do autor antes de registrar. Não gerar despacho automaticamente nem alterar autoria. |
| Média | Exportação em segundo plano para processos volumosos | Fila de tarefas e armazenamento temporário privado com expiração. Útil quando o volume superar a geração síncrona atual; requer worker e monitoramento, não apenas um botão. |

Não há necessidade de acrescentar serviços de IA, novos bancos ou mensageria para os ajustes entregues. As oportunidades acima são propostas, não funções já implementadas.

## Limites e critérios do download

Disponível aos perfis internos que já têm leitura do protocolo, respeitando cliente e acesso setorial. Não é um link público e não é disponibilizado automaticamente no Portal do Servidor. Despachos excluídos ficam fora. Documento indisponível ou com hash divergente impede um pacote parcial. Nomes de arquivo são normalizados, e as páginas compiladas não importam ações ou anotações interativas de PDFs enviados. Arquivos originais não são modificados.

Geração síncrona limitada a 200 arquivos, 64 MB de fontes, 500 páginas compiladas e 10.000 eventos. Exceder um limite retorna mensagem explícita; não há truncamento silencioso. Os downloads não ficam em cache público e não gravam cópias permanentes na aplicação.

Publicação exclusiva no visual para avaliação. Produção e development não fazem parte desta entrega.
