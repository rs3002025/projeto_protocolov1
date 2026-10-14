# Preparação para receber clientes — 14/10/2026

Estado: correções preparadas e testes locais aprovados; promoção e conferência dos ambientes em execução.

## Critérios de encerramento

- Mesma revisão Git em main, development e codex/visual-development; deployments bem-sucedidos e ativos.
- Mesma imagem Python fixada por digest e mesmos 45 pacotes efetivos, verificados contra requirements.lock na construção e na inicialização.
- Instalação exige hashes SHA-256 dos wheels aprovados; dependências diretas e transitivas sem versões flutuantes.
- Bibliotecas do navegador locais, fixadas e com integridade SHA-384; hashes conferidos pelo teste de integridade e auditoria npm sem vulnerabilidades conhecidas.
- Regressão conjunta, conferência de gráficos/QR/PDF e verificações de autorização e isolamento concluídas.
- Backup, autenticação, TLS, cookies seguros e isolamento de armazenamento conferidos, sem expor credenciais.

## Resultados confirmados até a preparação

- Regressão conjunta em banco temporário: 103 testes aprovados, 148 avisos de descontinuação, sem falha, 77,28 segundos.
- Auditoria atual do manifesto Python: 45 pacotes, nenhuma vulnerabilidade conhecida apontada.
- Auditoria npm da composição fixada: nenhuma vulnerabilidade conhecida apontada. Inclui html2pdf 0.14.0, jsPDF 4.2.1 e DOMPurify 3.4.17.
- Chart.js 4.5.1 e QRCode 1.0.0 locais. Bootstrap 5.1.3 interno e 5.3.3 no portal preservados para evitar alteração visual incidental.
- Provas de 13/10: SQL injection limitada no login, cookie falsificado, CSRF, travessia de diretório e acesso cruzado a protocolo/anexo bloqueados. Cliente fictício B preservado somente no visual, sem credenciais novas.
- Leitura física dos QR Codes confirmada pelo usuário; não permanece como pendência.
- Conta administrativa estava correta; Caps Lock causou a dificuldade de login. Nenhuma recuperação de senha foi executada.

## Limites da declaração

Não é certificação de teste de invasão exaustivo ou garantia de risco zero. A liberação técnica pressupõe criar cada cliente em organização própria, manter dados reais fora dos testes, conceder perfis mínimos e manter auditorias e backups durante a operação. Cadastros e dados de demonstração não são clientes reais.

As recomendações de dependências flutuantes e bibliotecas remotas estão implementadas nesta versão e serão encerradas após a publicação confirmada. Não declarar liberação final enquanto os critérios acima estiverem sem evidência.
