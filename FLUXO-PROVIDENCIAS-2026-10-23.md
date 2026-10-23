# Conclusão funcional do fluxo — 23/10/2026

Base preservada: e899cc4, incluindo exclusão administrativa auditada, atualização de Pillow, migração aditiva e alinhamento do cabeçalho. Não há nova alteração de esquema nesta entrega.

## Recursos

- Acompanhar/deixar de acompanhar: individual, para administrador e protocolista; mantém o processo em Meus processos após encaminhamento, sem alterar custódia.
- Encaminhamento simples por setor e pessoa opcional preservado. Envio para várias pessoas cria participações do mesmo processo, nunca cópias dele.
- Recebimento, transferência e conclusão independentes por participação. Tramitador não assume destinatário nominal alheio e não transfere nem conclui participação de outra pessoa. Administrador/protocolista mantêm intervenção conforme suas permissões.
- Histórico comum, cronológico e auditado identifica envolvidos em cada ação. Campos de responsável/localização exibem todas as participações abertas, sem substituir uns responsáveis por outros.
- Última providência concluída não finaliza o processo automaticamente. Administrador finaliza em Outras ações, com resultado opcional. Providências, recebimentos, complementos e retificações pendentes impedem finalização.
- Finalizado aparece também por texto, além do número verde na lista. O fluxo genérico de status não pode contornar a finalização administrativa nem transferir responsabilidade.
- Novas operações serializadas pelo bloqueio do protocolo no PostgreSQL; formulários de encaminhamento têm token contra reenvio. Destinatários validados integralmente antes de gravar.
- Exclusão permanece exatamente no fluxo publicado anteriormente, sem redefinir suas permissões, confirmação ou histórico. Nenhuma senha de usuário foi alterada.

## Validação

Suíte completa: **168 testes aprovados, 1 ignorado**, com dados fictícios e SQLite isolado; nenhum teste destrutivo em protocolos reais. Inclui migração idempotente, exclusão, desarquivamento, isolamento entre clientes, perfis, CSRF, recebimento nominal, transferência, conclusão independente, complementos, repetição de envio e preservação da numeração.

Chrome via complemento: prévia local com dados fictícios, organização do cabeçalho e acompanhamento conferidos. Ensaios SQLite não equivalem a teste de carga real de PostgreSQL. O teste ignorado depende de renderizador PDF local e não corresponde a mudança de PDF desta entrega.

Código enviado, checks e deploys ativos serão conferidos separadamente; um commit não é confirmação de implantação.
