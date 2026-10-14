# Bibliotecas locais do navegador

As bibliotecas são servidas por static/vendor, sem executar código de CDN em tempo de uso.
Versões e dependências transitivas: package.json e package-lock.json.
Arquivos, versões, SHA-256 e integridade SHA-384: static/vendor/manifest.json.

Para atualização controlada: npm ci --ignore-scripts, npm audit, npm run build.
O empacotador não roda no contêiner web. Os arquivos gerados e suas licenças são versionados.
Após mudar versões, atualize os hashes de integridade dos templates e confira gráficos,
QR Codes, relatórios e PDFs no navegador antes de promover a versão aos demais ambientes.

O bundle html2pdf utiliza jsPDF e DOMPurify nas versões explícitas do manifesto,
não uma cópia antiga incorporada em um bundle remoto.
