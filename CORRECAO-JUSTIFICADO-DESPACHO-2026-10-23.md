# Correção de alinhamento justificado do despacho

Causa reproduzida no renderizador: `white-space: pre-wrap` preservava espaços, mas impedia a distribuição correta entre palavras no alinhamento justificado. Atributo `text-align: justify` estava presente; o problema era sua interação com o CSS do corpo.

Correção: usar `pre-line` nos parágrafos, itens de lista e citações, mantendo quebras explícitas e permitindo a justificação. O mesmo estilo é usado na tela e no PDF.

Regressão adicionada: renderiza o template real e verifica a largura das linhas do parágrafo, exigindo que todas, exceto a última, ocupem a largura disponível. O teste falha com o estilo anterior e passa com o corrigido.

Não reescreve PDFs anteriores nem altera conteúdo, autoria ou registros de clientes. O ajuste se aplica aos próximos PDFs gerados.
