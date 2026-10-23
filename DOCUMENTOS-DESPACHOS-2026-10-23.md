# Documentos e exclusão administrativa de despachos

- Inclusão de documento sem seletor de substituição no topo.
- Ação Substituir junto a cada anexo atual; versões anteriores permanecem disponíveis para download.
- Exclusão de despacho restrita ao administrador, com confirmação explícita e motivo opcional.
- Exclusão lógica: texto e PDF preservados para auditoria, ocultos da listagem e com download normal bloqueado.
- Numeração dos despachos não é reutilizada; submissões repetidas não duplicam a exclusão.
- Escopo de cliente/protocolo, permissão no servidor e CSRF mantidos.
- Migração aditiva idempotente de três campos, sem apagar registros nem alterar senhas.

Validação local: 171 testes passaram, um teste de renderização PDF permaneceu ignorado por depender de bibliotecas nativas. Esta mudança não altera a geração nem o layout do PDF. A suíte inclui preservação de versões de anexos, exclusão, auditoria, permissões, isolamento e atualização de esquema legado.

A primeira execução de regressão encontrou restrições de acesso à pasta temporária do sandbox. A repetição com pasta temporária dedicada dentro do workspace passou integralmente, exceto pelo teste PDF já mencionado. Não houve uso de banco de clientes nos testes.
