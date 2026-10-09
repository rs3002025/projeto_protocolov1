# Homologação Muniprot — 09/10/2026

Este registro atualiza o plano consolidado sem apagar o histórico. O ciclo de homologação descrito abaixo foi concluído. Não constitui declaração de inexistência absoluta de vulnerabilidades.

## Implementação e publicação confirmadas

- Regressão conjunta: 90 testes aprovados em banco temporário; 143 avisos, sem falhas. Testes manuais complementares concluídos conforme evidências abaixo.
- Código f7fbc859d7cd97a4b89a76d14ef7d89301f3084f nas branches main, development e codex/visual-development. Railway confirmou Deployment successful e implantação ativa: produção 02852d2c-b98f-4790-8793-7d7512552088; desenvolvimento 26b8530f-a2d1-483f-8475-ea961df549dd; visual 9dc3392f-8b2d-4895-9e03-74dc8ab9ae0f.
- Atualização final de código d8a35231dfdb5506d521eb8d6f2940e639347006 confirmada ativa e bem-sucedida nos três ambientes: produção 8e0fa6f3-8da6-4cb7-b442-d0b5ad6f19bc; desenvolvimento 4d26917c-0642-4ce5-8a55-1283ca528b1c; visual 4d562c09-5c89-4bb5-911b-591ca03b7f27. O encerramento abaixo é uma atualização documental posterior, sem mudança funcional.
- Recebimentos inclui pedidos iniciais do portal, com restrição ao administrador/protocolista; PIN quando habilitado; responsável e status atualizados sem abrir o PDF na mesma página.
- Retificação conserva número e destinatário. Versões anteriores permanecem disponíveis no sistema interno, sem mudar o título do documento para estado ou versão.
- Consulta pública apresenta descrições compreensíveis, situação correta e eventos cronológicos no horário de Brasília. Conferida também com sessão de requerente: não redireciona indevidamente ao login administrativo.
- Login do portal identificado como Matrícula; dados funcionais e contas externas separados dos usuários internos; edição de contatos e confirmação de novo e-mail; importação completa com planilha-modelo de 15 campos.
- Auditoria administrativa ampliada com registros transacionais, sem incluir senhas, PINs ou tokens nos eventos. Testes de autorização e isolamento entre clientes aprovados.

## Homologação visual e recuperação concluídas

- Cadastro em etapas e confirmação por e-mail executados com conta fictícia; gestão funcional, elegibilidade, edição, portal e tela móvel conferidos.
- Protocolo real de teste 0007/2026 preservado em produção. Envio pelo servidor, recebimento e assinatura do protocolista, retificação, downloads e histórico conferidos no navegador.
- PDFs de envio e recebimento com duas páginas e retificação com uma página renderizados e inspecionados. Título fixo, dados funcionais, marcas do requerente e responsável nos respectivos espaços e dois QR Codes distintos. Horário exibido coincide com o registro UTC convertido para Brasília. Documentos antigos não foram regravados.
- Verificador público testado pelo navegador: PDF original aceito e cópia com alteração visível rejeitada. Evidência em tmp/homologacao-20261009/verificador-alterado-rejeitado.png. Ao selecionar outro arquivo, o resultado anterior agora é ocultado, evitando confusão antes da nova conferência. A leitura física dos QR Codes pela câmera não foi executada.
- Restauração nativa do snapshot de desenvolvimento executada: 110 protocolos, 30 históricos e 6.653 servidores preservados; novo volume montado e anterior conservado desmontado. Produção não foi restaurada.
- Backup independente de PostgreSQL e bucket restaurado em destinos temporários: 114 protocolos, 45 históricos e 10 objetos; hashes conferidos e destinos temporários removidos ao fim.
- Snapshots de produção com agendamento diário, semanal e mensal conferidos. PITR continua desligado em produção por decisão explícita; ativo em desenvolvimento. Snapshot do banco não substitui cópia do bucket.
- Inventário efetivamente instalado auditado nos três contêineres: 45 pacotes efetivos, nenhuma vulnerabilidade conhecida no resultado de pip-audit deste ciclo. Não equivale a teste de invasão ou garantia futura. Metadados legados do pip não foram declarados removidos.
- Certificado wildcard visual e suporte anteriormente aberto resolvidos; advertências de certificado não foram contornadas.

## Materiais de treinamento concluídos

Novos manuais em PDF (cliente: 9 páginas; administração geral: 10 páginas) e apresentações PowerPoint (cliente: 13 slides; administração geral: 15 slides), em português e com telas fictícias. Materiais antigos preservados. PDFs renderizados com Poppler e inspecionados; slides renderizados e conferidos, com validação de pacote e layout aprovada. Não foi necessária instalação do LibreOffice. Rascunhos Word não são entregues como documentos visualmente homologados. A renderização nativa do PowerPoint não foi executada.

Arquivos locais em training-artifacts/output, com sufixo “2026-10-09 final”. Relatórios de validação em training-artifacts/build-20261009/cliente-v3 e geral-v3; evidências de telas e auditoria em tmp/homologacao-20261009.

## Tramitação nominal homologada e perfil restaurado

- Com autorização expressa do usuário, consulta_qa recebeu temporariamente o perfil Tramitação e respostas / SEAD, somente no ambiente visual. A senha não foi alterada e o login ocorreu pelo fluxo normal.
- No protocolo fictício 0003/2026 (ID 10), o usuário diferente do destinatário nominal foi bloqueado, mesmo pertencendo ao mesmo setor. Após encaminhamento nominal para consulta_qa, o processo e a notificação de recebimento ficaram disponíveis ao destinatário.
- O destinatário registrou o recebimento e encaminhou à SEFIN. Após recebimento pelo administrador, o participante anterior continuou com acesso de consulta e download de anexo, sem permissão de tramitar ou receber novamente.
- Ao final, consulta_qa foi restaurado para Somente consulta / Sem setor. A configuração e a sessão ativa foram conferidas. Evidências: nominal-outro-usuario-bloqueado.png, nominal-destinatario-acesso.png e perfil-original-restaurado.png, em tmp/homologacao-20261009. Os movimentos de teste foram preservados no histórico.
- A antiga credencial de tramitador_qa foi recusada no login; essa conta não foi modificada. A prova foi concluída com a alternativa autorizada, sem contornar autenticação ou consultar hashes.

## Conclusão e limites

Não há correção conhecida de código nem prova manual deste ciclo aguardando execução. Isolamento entre clientes foi testado automaticamente; a prova nominal no navegador utilizou um cliente fictício e perfis distintos. Câmera física dos QR Codes, renderização nativa do PowerPoint e teste de invasão não foram executados e não são apresentados como homologados. Segurança exige manutenção e novas verificações ao longo do uso; ausência de vulnerabilidades conhecidas neste ciclo não significa risco zero.
