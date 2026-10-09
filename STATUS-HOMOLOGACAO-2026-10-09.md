# Homologação Muniprot — 09/10/2026

Este registro atualiza o plano consolidado sem apagar o histórico. Não constitui declaração de inexistência absoluta de vulnerabilidades. A homologação permanece aberta somente nos testes manuais explicitamente indicados abaixo.

## Implementação e publicação confirmadas

- Regressão conjunta: 90 testes aprovados em banco temporário; 143 avisos, sem falhas. A validação automatizada não substitui os testes manuais pendentes.
- Código f7fbc859d7cd97a4b89a76d14ef7d89301f3084f nas branches main, development e codex/visual-development. Railway confirmou Deployment successful e implantação ativa: produção 02852d2c-b98f-4790-8793-7d7512552088; desenvolvimento 26b8530f-a2d1-483f-8475-ea961df549dd; visual 9dc3392f-8b2d-4895-9e03-74dc8ab9ae0f.
- Recebimentos inclui pedidos iniciais do portal, com restrição ao administrador/protocolista; PIN quando habilitado; responsável e status atualizados sem abrir o PDF na mesma página.
- Retificação conserva número e destinatário. Versões anteriores permanecem disponíveis no sistema interno, sem mudar o título do documento para estado ou versão.
- Consulta pública apresenta descrições compreensíveis, situação correta e eventos cronológicos no horário de Brasília. Conferida também com sessão de requerente: não redireciona indevidamente ao login administrativo.
- Login do portal identificado como Matrícula; dados funcionais e contas externas separados dos usuários internos; edição de contatos e confirmação de novo e-mail; importação completa com planilha-modelo de 15 campos.
- Auditoria administrativa ampliada com registros transacionais, sem incluir senhas, PINs ou tokens nos eventos. Testes de autorização e isolamento entre clientes aprovados.

## Homologação visual e recuperação concluídas

- Cadastro em etapas e confirmação por e-mail executados com conta fictícia; gestão funcional, elegibilidade, edição, portal e tela móvel conferidos.
- Protocolo real de teste 0007/2026 preservado em produção. Envio pelo servidor, recebimento e assinatura do protocolista, retificação, downloads e histórico conferidos no navegador.
- PDFs de envio e recebimento com duas páginas e retificação com uma página renderizados e inspecionados. Título fixo, dados funcionais, marcas do requerente e responsável nos respectivos espaços e dois QR Codes distintos. Horário exibido coincide com o registro UTC convertido para Brasília. Documentos antigos não foram regravados.
- Restauração nativa do snapshot de desenvolvimento executada: 110 protocolos, 30 históricos e 6.653 servidores preservados; novo volume montado e anterior conservado desmontado. Produção não foi restaurada.
- Backup independente de PostgreSQL e bucket restaurado em destinos temporários: 114 protocolos, 45 históricos e 10 objetos; hashes conferidos e destinos temporários removidos ao fim.
- Snapshots de produção com agendamento diário, semanal e mensal conferidos. PITR continua desligado em produção por decisão explícita; ativo em desenvolvimento. Snapshot do banco não substitui cópia do bucket.
- Inventário efetivamente instalado auditado nos três contêineres: 45 pacotes efetivos, nenhuma vulnerabilidade conhecida no resultado de pip-audit deste ciclo. Não equivale a teste de invasão ou garantia futura. Metadados legados do pip não foram declarados removidos.
- Certificado wildcard visual e suporte anteriormente aberto resolvidos; advertências de certificado não foram contornadas.

## Materiais de treinamento concluídos

Novos manuais em PDF (cliente: 9 páginas; administração geral: 10 páginas) e apresentações PowerPoint (cliente: 13 slides; administração geral: 15 slides), em português e com telas fictícias. Materiais antigos preservados. PDFs renderizados com Poppler e inspecionados; slides renderizados e conferidos, com validação de pacote e layout aprovada. Não foi necessária instalação do LibreOffice. Rascunhos Word não são entregues como documentos visualmente homologados. A renderização nativa do PowerPoint não foi executada.

Arquivos locais em training-artifacts/output, com sufixo “2026-10-09 final”. Relatórios de validação em training-artifacts/build-20261009/cliente-v3 e geral-v3; evidências de telas e auditoria em tmp/homologacao-20261009.

## Duas pendências manuais específicas

1. **Tramitação nominal e acesso de participantes anteriores no navegador.** Regras implementadas e testadas automaticamente. A conta consulta_qa foi acessada e restrições administrativas conferidas. A credencial original de tramitador_qa, recuperada do histórico de criação, foi recusada no login normal; estado ativo e vínculo foram conferidos sem expor hash. Não houve acesso por sessão artificial nem alteração de senha por fora do fluxo. Necessário restabelecer a credencial pelo titular/administrador para terminar o teste visual com esse perfil. Não pedir ao usuário que adivinhe uma senha criada pelo agente.
2. **Envio do PDF original e alterado no verificador público pelo navegador.** Tela pública e identificação da emissão conferidas; integridade testada automaticamente. A seleção do arquivo pela extensão retornou sem arquivo selecionado. Necessário habilitar/confirmar “Allow access to file URLs” na extensão ChatGPT antes de repetir a prova visual. Não declarar como concluído o upload que não ocorreu nem a leitura física dos QR Codes pela câmera.

Não há outra correção conhecida de código aguardando implementação neste registro. Essas duas provas impedem afirmar que toda a homologação manual terminou. Alterações adicionais encontradas devem ser incorporadas sem abandonar o andamento principal.
