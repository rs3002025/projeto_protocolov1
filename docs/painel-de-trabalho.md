# Painel de trabalho — avaliação no visual

Esta versão foi preparada para avaliação no ambiente visual. Não é autorização de publicação em produção ou desenvolvimento.

## Diagnóstico do painel anterior

O painel priorizava filtros, impressão e gráficos antes da rotina. Não oferecia uma fila com acesso direto aos processos. Misturava contadores fixos com indicadores filtrados, apresentava conclusões pelo período de criação sem explicar esse recorte, desconsiderava setores paralelos na distribuição e limitava a opção de evolução histórica a 2025 em diante. A página também carregava todos os gráficos ao entrar.

## Nova organização

- Cabeçalho pessoal, busca por número e criação de protocolo conforme permissão.
- Visão da equipe ou Minha fila para gestores. Tramitadores veem seu atendimento, recebimentos nominais ou compartilhados do setor e casos legados em que já podem atuar. Consulta permanece somente leitura.
- Cartões da visão selecionada: processos em aberto, para receber, prazos vencidos e documentos pendentes. Cartões abrem a fila correspondente; cada processo conta uma vez, independentemente do número de participações.
- Fila paginada com requerente, número, situação, localização atual, prazo e acesso ao atendimento. Recebimento não é executado por um link do painel.
- Filas separadas para recebimentos, pedidos recebidos aguardando análise, responsabilidade pessoal, pendências documentais, acompanhamento e conclusão administrativa. Acompanhamento não é responsabilidade; participações antigas ou concluídas não geram pendências atuais.
- Prazos de hoje aos próximos sete dias, com acesso ao processo e consulta dos casos sem prazo definido. Datas calculadas em Brasília. Processos concluídos, arquivados e excluídos não entram nas filas ativas.
- Últimas atualizações dos processos acessíveis, sem alegar leitura/não leitura nem exibir observações privadas.
- Indicadores do acervo em área recolhida, carregada apenas ao abrir. Filtros analíticos não modificam a fila operacional e isso é explicado na tela. Impressão personalizada preservada para perfis com relatórios.

## Semântica dos indicadores

Na análise histórica, as datas são datas do pedido: o cartão de concluídos diz explicitamente que são pedidos daquele recorte já concluídos, e não conclusões realizadas naquele período. Todo o acervo inclui datas anteriores a 2025. Setores atuais incluem participações paralelas, inclusive destinos pendentes; um mesmo processo pode contar em mais de um setor, mas não é duplicado no total geral. Os links dos cartões mantêm período, tipo exato, situação e setor.

## Segurança e implementação

Consultas partem do acesso existente e são isoladas por organização. Não há alteração de permissões, senhas, protocolos ou registros de auditoria. A página principal é renderizada no servidor e permanece utilizável sem os gráficos/JavaScript. Filas e páginas são validadas; datas analíticas inválidas retornam erro de entrada. Rótulos e dados livres permanecem escapados. As consultas de localização e responsabilidade usam o último movimento de cada participação ativa. Os dados são consultados ao abrir ou navegar, sem prometer atualização em tempo real.
