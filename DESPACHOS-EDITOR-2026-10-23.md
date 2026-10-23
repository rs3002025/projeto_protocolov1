# Despachos: lista compacta, assunto e editor

- Lista fechada por padrão: número, assunto e nome do autor. Texto, setor, horário e ações aparecem ao abrir.
- Tela própria de escrita, assunto obrigatório (250 caracteres) e editor com fontes, tamanhos, cores, títulos, negrito, itálico, sublinhado, tachado, listas, alinhamento, recuo, citação, links, desfazer/refazer e ampliação.
- Conteúdo estruturado Delta validado no servidor. HTML/CSS não são aceitos diretamente; os elementos renderizados são gerados por código com escape, formatos e URLs permitidos. Imagens e incorporações são recusadas.
- Texto simples permanece como snapshot e alternativa se o JavaScript não carregar.
- Falha transitória preserva assunto, texto, formatação e token de envio.
- PDF incorpora assunto e a mesma formatação. PDFs anteriores não são regenerados ou sobrescritos.
- Migração aditiva: assunto e conteudo_delta. Despachos antigos ficam com assunto não informado, sem inventar conteúdo.
- Editor Quill 2.0.2 fixado, servido localmente com SRI, dependências bloqueadas e licenças preservadas. A tentativa com 2.0.3 foi rejeitada pelo npm audit (GHSA-v3m3-f69x-jf25); a versão 2.0.2 não teve apontamentos no audit. Não usamos a exportação HTML do Quill.
- Referência do alerta: https://github.com/advisories/GHSA-v3m3-f69x-jf25

Validação: regressão de 177 testes, incluindo renderização PDF real; testes de formatação, texto legado, scripts/HTML/URLs maliciosas, assunto, permissões, isolamento, repetição e preservação em falha. Foi necessário atualizar a quantidade esperada de arquivos no manifesto de integridade de seis para oito pela inclusão dos dois arquivos do editor.

PDF fictício de três páginas renderizado pelo WeasyPrint local 69.0 com bibliotecas nativas já existentes, convertido em PNG pelo Poppler e conferido página a página. Produção permanece com WeasyPrint 70.0 bloqueado no manifesto, sem alterar dependências Python.
