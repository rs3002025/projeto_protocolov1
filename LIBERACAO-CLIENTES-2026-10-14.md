# Preparação para receber clientes — 14/10/2026

Estado: ciclo concluído. Produção, desenvolvimento principal e visual sincronizados e tecnicamente liberados para receber clientes no escopo homologado. Nenhuma pendência bloqueadora conhecida dos planos ou da avaliação permanece aberta.

## Critérios de encerramento

- Mesma revisão Git em main, development e codex/visual-development; deployments bem-sucedidos e ativos.
- Mesma imagem Python fixada por digest e mesmos 45 pacotes efetivos, verificados contra requirements.lock na construção e na inicialização.
- Instalação exige hashes SHA-256 dos wheels aprovados; dependências diretas e transitivas sem versões flutuantes.
- Bibliotecas do navegador locais, fixadas e com integridade SHA-384; hashes conferidos pelo teste de integridade e auditoria npm sem vulnerabilidades conhecidas.
- Regressão conjunta, conferência de gráficos/QR/PDF e verificações de autorização e isolamento concluídas.
- Backup, autenticação, TLS, cookies seguros e isolamento de armazenamento conferidos, sem expor credenciais.

## Resultados confirmados até a preparação

- Regressão final conjunta em banco temporário: 104 testes aprovados, 148 avisos, sem falha, 60,19 segundos. Avisos de descontinuação e o ZIP adulterado intencionalmente não representam teste reprovado.
- Auditoria atual do manifesto Python: 45 pacotes, nenhuma vulnerabilidade conhecida apontada.
- Auditoria npm da composição fixada: nenhuma vulnerabilidade conhecida apontada. Inclui html2pdf 0.14.0, jsPDF 4.2.1 e DOMPurify 3.4.17.
- Chart.js 4.5.1 e QRCode 1.0.0 locais. Bootstrap 5.1.3 interno e 5.3.3 no portal preservados para evitar alteração visual incidental.
- Provas de 13/10: SQL injection limitada no login, cookie falsificado, CSRF, travessia de diretório e acesso cruzado a protocolo/anexo bloqueados. Cliente fictício B preservado somente no visual, sem credenciais novas.
- Leitura física dos QR Codes confirmada pelo usuário; não permanece como pendência.
- Conta administrativa estava correta; Caps Lock causou a dificuldade de login. Nenhuma recuperação de senha foi executada.

## Limites da declaração

Não é certificação de teste de invasão exaustivo ou garantia de risco zero. A liberação técnica pressupõe criar cada cliente em organização própria, manter dados reais fora dos testes, conceder perfis mínimos e manter auditorias e backups durante a operação. Cadastros e dados de demonstração não são clientes reais.

## Publicação e provas finais

- Código funcional a2b0bc4cd307bdbdaadd782998020bef48dac852 publicado nas três branches. Deployments ativos e bem-sucedidos: produção fda41117-d8cf-4651-a40a-be1d9d0bf8d0; desenvolvimento 4d6a1146-ac96-4da0-824c-31b28d7a7ba1; visual 7e2a04a9-7589-4f1e-b392-c08ac5c570ff. Atualizações documentais posteriores não modificam esse código funcional.
- Logs de inicialização dos três contêineres: 45 pacotes, locked=true e impressão idêntica 5c5d2b18a1dbed71482f01dc53123c0c8db3a0f0385370cc8eb1afdda7ee3678. Isso encerra a divergência de dependências efetivamente instaladas observada em 13/10. Manifesto auditado novamente em 14/10, sem vulnerabilidades conhecidas.
- HTTPS /health retornou 200 e database=ok nos três ambientes. HSTS, nosniff e CSP ativos; CSP deixou de autorizar CDNs de bibliotecas. Compatibilidade com os scripts inline existentes preservada, não apresentada como CSP sem inline.
- JavaScript publicado idêntico nos três domínios, SHA-256 3a62083cb977fb614586c80ed22d0a059687d4599b133ed34f9ec7d00244ebf5. Seis bibliotecas locais conferidas por SHA-256/SRI na regressão. Painéis autenticados carregaram; nenhuma mensagem de erro JavaScript observada nas conferências finais.
- PDF real do dashboard gerado no Chrome com jsPDF 4.2.1: inicialmente identificado gráfico cortado; corrigidas dimensões de impressão e proteção de quebra. Nova geração A4, uma página, 289.013 bytes, renderizada e inspecionada integralmente; três gráficos completos. Evidência: tmp/liberacao-20261014/dashboard-corrigido-1.png.
- Requerimento longo fictício 0003/2026 do visual aberto pelo botão do sistema em outra aba; quatro páginas inspecionadas no visualizador, QR de acompanhamento, título fixo e campos de assinatura presentes. Não foi efetuada assinatura ou alteração de credencial. Provas anteriores de assinatura, retificação, integridade e dois QR Codes continuam preservadas.
- Entrada prefeitura.visual.muniprot.com.br/portaldoservidor abriu diretamente o Portal do Servidor, com Matrícula e Senha, sem menu de escolha de área. Recursos opcionais e dados de cada cliente/ambiente continuam independentes: sincronização de código não ativa capacidades nem copia bancos.
- Backups de produção reconferidos no Railway: diário recente (15 horas, 120 MB), semanal e mensal disponíveis. Restauração nativa e backup independente de banco/bucket permanecem homologados pelo registro de 09/10; não foi restaurada produção nesta rodada. PITR em produção não foi ativado.
- Avaliação defensiva de 13/10 encerrada pelas correções e verificações acima. Tentativas limitadas e autorizadas não obtiveram acesso indevido, elevação de privilégio ou dados de outro cliente. Não foram feitos testes destrutivos, sobrecarga ou exploração ativa em produção.
- Materiais finais de treinamento de 09/10 preservados; este ciclo altera infraestrutura de dependências e paginação do relatório, não o fluxo documentado de cadastro, PIN, recebimento e tramitação. Arquivos de teste preservados para consulta.

## Operação após a liberação

Continuar backups, auditorias de dependências e revisão de permissões durante o uso é manutenção normal, não uma tarefa bloqueadora deste ciclo. A ausência de achados nos testes realizados não certifica invulnerabilidade nem substitui avaliação independente mais ampla.
