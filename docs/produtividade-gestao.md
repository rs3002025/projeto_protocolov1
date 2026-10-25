# Produtividade e indicadores — visual

## Funções

- Indicadores em Relatórios → Indicadores de gestão, com período configurável, comparação de entradas e conclusões, tempo médio até conclusão e tempos por setor. Gráfico diário até 92 dias; períodos maiores agrupam por mês. Datas sem registros aparecem com zero. Excel inclui séries, setores e critérios.
- Pesquisas salvas por usuário e cliente, até 20 ativas. Mantêm os filtros, não a página de resultados nem um destino externo. Remover desativa o atalho; salvar novamente com o mesmo nome atualiza/reativa.
- Modelos de despacho compartilhados pelo cliente, administrados por quem possui permissão de gerenciamento. Usam o mesmo editor formatado. Protocolistas e tramitadores podem aplicar modelos ativos ao incluir um despacho, somente em processos nos quais já podem atuar. A aplicação preenche um rascunho, não registra despacho nem reaproveita a autoria.
- Alertas de prazo no painel, por usuário e cliente: hoje, amanhã, três ou sete dias, sempre incluindo vencidos. Podem ser pausados. Seguem Equipe, Minha fila ou Acompanhando. Não enviam e-mail/push e não geram janelas repetidas.
- Recuperação de documento original em Configurações, apenas para administradores. Aceita exclusivamente bytes com tamanho e SHA-256 iguais aos metadados existentes e, quando houver, à evidência de emissão. Recusa substituir arquivo já íntegro. Recupera uma cópia no banco mantendo objeto de armazenamento anterior, ID, nome, versão e evidências; registra a operação na auditoria.

## Critérios dos indicadores

Entradas usam a data do pedido. Conclusões usam finalizado_em, a data de conclusão registrada no sistema, apresentada em Brasília; não se deduz uma data a partir do status. Encerrados sem esse marco são informados separadamente em todo o acervo acessível. A média até conclusão usa dias corridos apenas quando pedido e conclusão são válidos e cronologicamente consistentes.

Os setores são selecionados pela data de envio do encaminhamento. Espera é envio até recebimento. Atendimento é recebimento até a primeira saída/encerramento válida. A transferência seguinte é considerada mesmo se estiver fora do período consultado. Atendimentos ainda abertos ou sem marco final não entram na média de atendimento encerrado; a base de cada média é mostrada. Durações negativas são excluídas. Encaminhamentos encerrados ou substituídos não reaparecem como pendentes atuais. Participações paralelas contam separadamente, não como total único de protocolos.

Todos os horários partem de UTC e são apresentados em Brasília. Informações históricas sem os marcos necessários não recebem precisão fictícia.

## Persistência e isolamento

Três novas tabelas com tenant_id e chaves de usuário/cliente: pesquisas_salvas, preferencias_alerta e modelos_despacho. O bootstrap cria tabelas de forma idempotente; em PostgreSQL, um advisory lock serializa a atualização entre réplicas. Nenhuma senha ou permissão de usuário é alterada. POSTs usam a proteção CSRF existente. Não há novo serviço externo ou dependência Python.

Publicação somente no visual. Produção e development permanecem fora desta atualização.
