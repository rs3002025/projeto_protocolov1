# Situação do processo e tramitação

A situação é geral do processo. O recebimento, o responsável e a conclusão de cada participação são controles separados, apresentados na área de tramitação. Quando há vários destinatários, mudar a situação geral não recebe nem conclui as participações das outras pessoas.

| Situação | Quando é registrada |
|---|---|
| Protocolo gerado | Cadastro direto pela equipe de protocolo. O criador já responde pelo cadastro; não há recebimento separado de si próprio. |
| Aguardando recebimento | Entrada pelo Portal do Servidor quando a assinatura eletrônica do protocolista está habilitada, ainda aguardando a confirmação com PIN. |
| Recebido | Sem assinatura eletrônica habilitada, a entrada pelo portal é recebida automaticamente pelo sistema. Com assinatura, resulta da confirmação do protocolista. Também é usado após o recebimento dos encaminhamentos ou dos documentos solicitados, sem afirmar que uma análise começou. |
| Em tramitação | Novo encaminhamento para outro setor ou usuário. Se ainda há participações aguardando recebimento, a situação permanece assim até um responsável registrar o início do trabalho ou todos os encaminhamentos ativos serem recebidos. |
| Em análise | Registrada explicitamente por quem pode atuar no processo. Também é a situação da retomada de análise pelo desarquivamento. Apenas receber, concluir uma participação ou incluir um despacho não inicia análise automaticamente. |
| Pendente de documento | Registrada por quem está atuando no processo ou automaticamente ao solicitar complemento pelo portal. Outro recebimento/encaminhamento não apaga uma solicitação formal ainda pendente. Quando todas essas solicitações forem atendidas, volta a Recebido para conferência, ou Em tramitação se ainda houver destinatários aguardando recebimento. |
| Concluído | Ação administrativa Concluir processo, após regularizar as pendências. Concluir uma participação isolada não conclui o processo. Finalizado é apenas o valor histórico compatível desta mesma situação. |
| Aguardando conclusão | Todas as participações já foram concluídas, mas falta o encerramento administrativo do processo. Não volta a Recebido nem é concluído automaticamente. Uma pendência documental ainda aberta prevalece sobre essa situação. |
| Arquivado | Ação própria de arquivamento. Não é oferecida como simples mudança de situação. |

## Atualização durante a tramitação

O fluxo considera apenas participações ativas, nunca quem apenas acompanha nem participações já concluídas. Com um responsável ativo, aparece somente Encaminhar. Com dois ou mais, o responsável recebido vê somente Concluir minha participação; o servidor também bloqueia encaminhamentos nesse estágio. Quando resta um responsável ativo, o formulário de encaminhamento volta automaticamente. Recebimentos pendentes continuam exigindo confirmação. O administrador pode concluir o processo com o último atendimento recebido, encerrando-o na mesma ação, desde que não existam outras pendências.

O encaminhamento coletivo é uma opção secundária do formulário individual, não uma etapa obrigatória. Os registros de participações anteriores permanecem no histórico. Concluir processo e Atualizar status são ações separadas, com suas permissões próprias.

Exceção de gestão: administradores e protocolistas podem encaminhar novamente mesmo após um envio ou enquanto houver vários responsáveis ativos. Sem uma participação recebida selecionada, a intervenção acrescenta um encaminhamento sem apagar os anteriores, concluir participações ou fabricar recebimentos. A autoria da intervenção fica registrada no histórico. A regra de um/vários responsáveis continua valendo para os demais usuários. Processos concluídos ou arquivados precisam ser reabertos; o recebimento inicial com assinatura também não é dispensado.

Versões de PDF são controle interno: não existe comando manual para gerar versões extras. Ao corrigir os dados de um requerimento sem assinatura, seu PDF já registrado é atualizado automaticamente, preservando o anterior no histórico de documentos. Salvar sem alterar conteúdo não gera nova cópia. Documentos assinados continuam sujeitos à retificação própria.

O botão Atualizar status está na lista e na página do processo. Permite marcar Em análise ou Pendente de documento, com observação e registro de autoria no histórico, sem mudar a custódia. Fica disponível ao responsável por uma participação recebida; administradores e protocolistas também podem atuar sobre participações recebidas. Usuários somente de consulta e participantes que ainda não receberam não podem usar a ação.

Receber, encaminhar, concluir e arquivar continuam sendo ações próprias: não é possível simular essas operações escolhendo um texto no campo de situação. Processos concluídos/arquivados não podem ser reabertos por esse campo.

Um novo encaminhamento registra Em tramitação, exceto se ainda há solicitação formal de documentos pendente no portal: nesse caso prevalece Pendente de documento. Receber ou concluir outra participação preserva Em análise ou Pendente de documento quando o responsável tiver registrado explicitamente uma dessas situações. A pendência documental deve ser regularizada antes de concluir ou arquivar o processo.

## Assinatura eletrônica

Sem assinatura eletrônica habilitada, o pedido externo entra automaticamente como Recebido e não exige clique ou PIN do protocolista. O evento identifica o Sistema, sem fabricar assinatura nem recebimento humano. O pedido fica sob a equipe de protocolo, com atalho Recebidos aguardando análise no painel. Ao iniciar a análise ou solicitar documentos, a pessoa que realiza a ação fica identificada como responsável quando ainda não há responsável individual nem participações.

Com assinatura habilitada, permanece Aguardando recebimento até a confirmação do protocolista com PIN. Ligar a assinatura posteriormente não exige reassinar pedidos já recebidos. Desligá-la regulariza automaticamente os pedidos externos ainda aguardando recebimento, com histórico preservado e sem regravar os PDFs.

Registros fechados, excluídos, já recebidos ou de outros tipos de abertura não são reclassificados pelo recebimento automático. O recebimento de um encaminhamento por outro setor/usuário continua sendo confirmado pelo destinatário: é uma operação distinta da entrada inicial pelo portal.
