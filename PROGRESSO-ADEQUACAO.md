# Adequação ao Projeto Básico — andamento

## 04/09/2026 — primeiro conjunto

Enviado somente à branch development: 3bd7d4a0c3d1fea499e8d5b9f6bd06f75bcebc34.

- CSRF global, tokens nos formulários manuais e cabeçalho nas requisições de atualização.
- Observações e resultados de busca renderizados como texto, não HTML.
- Consulta pública não revela o número no título antes da matrícula; janela expirada reutiliza o registro e matrícula Unicode não causa erro.
- Relatórios e exportação passam a exigir a permissão reports.
- Suíte isolada em SQLite temporário, com trava antes de recriar tabelas e fechamento das conexões.
- 11 testes automatizados passaram.
- Navegador integrado, servidor local: login, tramitação para Jurídico e recebimento confirmados; não equivale à homologação do Railway.

## Pendências

## 04/09/2026 — versionamento documental

Commit development b40061604fb0e59eca464211d0ec4c774a4a8203. Railway confirmou ACTIVE / Deployment successful, implantação 32918a13-6818-4dd3-95e6-15e4ce2e3ead.

- Upload permite novo documento ou nova versão; mantém todos os arquivos e downloads anteriores.
- Registra autor, data e evento no histórico. Serializa uploads por protocolo com bloqueio de linha no PostgreSQL (concorrência real ainda não homologada).
- Não agrupa indevidamente os arquivos legados que compartilhavam a chave padrão.
- Desativa exclusão permanente de anexos/protocolos para preservar a trilha. Arquivamento continua disponível.
- Impede anexação em processo arquivado; rejeita arquivos vazios ou acima de 20 MB.
- 14 testes passaram. Pelo navegador integrado, uploads reais de dois arquivos confirmaram v1/v2, autor, horário e links separados.
- Ainda não há homologação autenticada no Railway nem versionamento de PDFs gerados automaticamente.

## Pendências restantes

## 08/09/2026 — integridade do processo e identidade institucional

- Commit 34ff31f834920ef38cb327bc4981f2c69457af86: numeração definida no servidor e serializada por organização no PostgreSQL; criação e histórico atômicos; estados oficiais padronizados; encaminhamento antigo removido da interface; arquivamento bloqueado com recebimento pendente; arquivado somente leitura; edições registram campos e valores modificados; bootstrap normaliza estados legados.
- Commit 7dd1b86a8e5d84fce0289e76cebb4fa2be63f030: município, órgão/unidade e rodapé configuráveis e isolados por cliente; ambos os modelos de documento usam esses dados; referências fixas à Secretaria da Administração e ao rodapé de outra prefeitura removidas.
- 22 testes passaram. A geração binária por WeasyPrint não roda neste Windows sem as bibliotecas GTK; o template do PDF foi renderizado em teste. A rota deverá ser homologada no contêiner Linux do Railway.

## 08/09/2026 — integridade do processo

- Commit 34ff31f834920ef38cb327bc4981f2c69457af86, somente em development.
- Número passa a ser definido exclusivamente pelo servidor; bloqueio da organização serializa a sequência por cliente no PostgreSQL; protocolo e evento de criação são gravados na mesma transação.
- Estados canônicos: PROTOCOLO GERADO, EM ANÁLISE, PENDENTE DE DOCUMENTO, FINALIZADO, CONCLUÍDO, EM TRAMITAÇÃO e ARQUIVADO. Bootstrap normaliza registros antigos.
- Encaminhamento antigo por responsável removido da interface. Tramitação permanece exclusivamente entre setores, com envio e recebimento.
- Arquivamento exige inexistência de tramitação pendente; processo arquivado não aceita edição nem alteração genérica de estado.
- Histórico de edição descreve os campos e valores alterados.
- 21 testes aprovados. A concorrência precisa ser homologada no PostgreSQL do Railway; SQLite não reproduz bloqueio de linha.

## 08/09/2026 — relatórios, prazos, estatísticas e usuários

- Commit 704fdf4424528864574c82139b5e97752c41bcfd: filtros unificados entre listagem, relatório e Excel; datas validadas; paginação preserva filtros; painel contabiliza prazos vencidos pelo campo prazo_em; estatísticas por setor atual; dashboard compatível com SQLite nos testes.
- Commit bfff4a940f22629852f3c6be99d0bdbb5e990332: administrador edita nome, e-mail, perfil e setor, desativa/reativa usuários, sem atravessar clientes; protege a própria conta e mantém ao menos um administrador ativo; conta inativa deixa de ser carregada pela sessão.
- 18 testes passaram. Painel e tela completa de usuários conferidos visualmente no navegador local.
- Ambos publicados somente em development; implantação e homologação autenticada no Railway ainda precisam ser confirmadas.

- Implantação confirmada no Railway: ACTIVE / Deployment successful, ID 81fe813b-8bf3-49d2-a71d-3cd3cf728198. Falta homologação autenticada; aba do Chrome permanece no login.
- Numeração concorrente; versionamento dos documentos gerados; histórico de edições; coerência de tramitação/arquivamento.
- Alertas/visões adicionais de prazos, consistência de status e demais verificações de segurança.
- Parametrização municipal e revisão visual dos documentos.
- Backup/restauração, disponibilidade e organização de suporte e capacitação.
- Teste local revelou incompatibilidade do dashboard com SQLite (cast de data); ainda não alterada. No Railway é PostgreSQL.
- Janela estreita do navegador integrado mostrou navegação horizontal cortada; revisar responsividade.

Não há declaração de atendimento integral nem de ausência de vulnerabilidades. Produção não foi alterada.
