# Autorizações de protocolos

A capacidade começa desativada e é habilitada pelo administrador geral em **Clientes → Capacidades → Autorização de protocolos**, individualmente por organização. O administrador do cliente não pode habilitar a capacidade por sua conta.

Com a capacidade habilitada, o administrador do cliente pode criar uma conta com perfil **Autorizador** ou marcar **Autorizador** em um usuário interno existente. O perfil dedicado tem sua própria fila e só consulta os processos que lhe foram atribuídos. A função adicional preserva as demais atribuições do usuário.

No protocolo, o responsável seleciona o autorizador e aciona **Solicitar autorização**. Não há descrição nem justificativa adicional. A solicitação guarda um resumo do protocolo e a identificação dos anexos disponíveis no envio. O responsável e o setor do protocolo não são alterados.

Enquanto há uma autorização pendente, o servidor bloqueia alterações, encaminhamentos, recebimentos, conclusão, arquivamento, exclusão e substituição de documentos, inclusive quando solicitados por links antigos ou APIs. Consulta, downloads e acompanhamento pessoal permanecem disponíveis. O autorizador selecionado pode acrescentar um despacho pelo editor existente e anexar documentos próprios à análise, sem modificar o requerimento original.

Em **Autorizações**, cada autorizador encontra sua fila com paginação e filtros de situação. Ao abrir uma solicitação, vê requerente, resumo do pedido, requerimento, anexos e despachos. Pode escolher **Autorizar** ou **Não autorizar** sem preencher qualquer outro campo. Despachos e anexos são opcionais.

As duas decisões geram um PDF com identidade visual do cliente, número do protocolo, requerente, decisão, identificação do usuário, setor quando existente, data e hora de Brasília. O PDF é armazenado com hash de integridade e permanece disponível para o responsável e para o autorizador. A decisão e seu documento não são sobrescritos; pedidos posteriores criam novos registros. O documento é um registro da decisão no sistema, seguindo o mecanismo documental dos despachos, sem declarar assinatura eletrônica adicional.

O desbloqueio e a decisão são gravados na mesma transação do documento e do histórico auditado. Se a geração ou o armazenamento do PDF falhar, a solicitação continua pendente e o processo segue bloqueado, permitindo nova tentativa. Envios repetidos e decisões concorrentes não geram documentos ou eventos duplicados. Existe também um índice único parcial para impedir duas solicitações pendentes para o mesmo protocolo.

A negativa não encerra nem arquiva o protocolo: o responsável continua com o processo e decide os próximos passos. O estado operacional anterior é preservado e volta a aparecer quando a autorização termina. Enquanto está pendente, as telas indicam **Aguardando autorização**.

Não é permitido desativar a capacidade, remover a função ou desativar um autorizador enquanto ele tiver solicitações pendentes. Concluídas as solicitações, a configuração pode ser alterada normalmente.

O histórico e os documentos seguem as configurações de visibilidade externa já existentes. No Portal do Servidor configurado para somente situação, os documentos internos da análise não são expostos. Documentos de autorização e da análise não são incorporados ao requerimento original, mas integram a cópia completa do processo.

## Atualização do banco

O bootstrap acrescenta a capacidade às organizações e a seu histórico de capacidades, a função aos usuários e cria a tabela `autorizacoes_protocolos`. É idempotente, preserva os registros existentes e não ativa a capacidade para nenhum cliente automaticamente.

## Validação

`tests/test_authorizations.py` verifica os dois resultados, custódia, bloqueio das operações, acesso nominal, papéis, habilitação por cliente, CSRF, arquivos, documento real e recuperação após falha. Os testes de bootstrap simulam banco antigo e reinícios.

`scripts/qa_postgres_authorizations.py` só aceita o banco descartável local `muniprot_qa`, usuário `qa`. Verifica solicitações concorrentes, decisões concorrentes, rollback por falha no PDF, unicidade do documento e cadeia de auditoria. O workflow funcional executa essa verificação em PostgreSQL 16.
