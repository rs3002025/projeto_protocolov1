# Plano de evolução visual e de usabilidade — Sysprot+

## 1. Finalidade

Este documento é a referência permanente para a modernização visual e a melhoria de usabilidade do Sysprot+. O trabalho será realizado inicialmente em ambiente isolado, sem alterar a produção nem o ambiente principal de desenvolvimento.

## 2. Ambientes e isolamento

- **Produção:** permanece inalterada até aprovação e homologação expressas.
- **Desenvolvimento principal:** permanece disponível para correções funcionais e não receberá os experimentos visuais.
- **Branch visual:** `codex/visual-development`.
- **Ambiente Railway:** `visual-development`, ligado exclusivamente à branch visual.
- Alterações visuais somente serão promovidas para os demais ambientes depois de revisão, testes e autorização.

## 3. Diagnóstico atual

O sistema atende ao fluxo funcional, porém sua interface ainda apresenta características de módulos construídos separadamente, sem um sistema visual uniforme. Isso aumenta o esforço de aprendizagem, dificulta a identificação das ações mais importantes e reduz a qualidade da experiência em telas menores.

### 3.1 Estrutura e navegação

- Cabeçalho alto, dividido em duas faixas, consumindo área útil.
- Logo, nome do sistema e menu pessoal não formam uma composição equilibrada.
- O usuário é representado apenas por um emoji, sem nome, perfil ou organização visíveis.
- O item ativo da navegação não possui destaque suficiente.
- No celular, a navegação ultrapassa a largura disponível; foi constatado menu com aproximadamente 729 px dentro de uma área útil de cerca de 375 px.
- Não há menu móvel recolhível.
- Configurações importantes ficam escondidas no menu pessoal.

### 3.2 Consistência visual

- Títulos usam níveis e tamanhos diferentes entre as telas.
- Cartões, botões, tabelas, filtros e espaçamentos não seguem um padrão único.
- O verde domina o cabeçalho, enquanto o conteúdo é quase inteiramente cinza e branco.
- As cores dos botões não comunicam de forma consistente a importância ou o risco das ações.
- Os status não possuem uma semântica visual padronizada.
- Há grandes áreas vazias, especialmente na tela de detalhes.

### 3.3 Dashboard

- Os indicadores não funcionam claramente como atalhos para as respectivas listas.
- Impressão recebe destaque semelhante ou superior às ações operacionais.
- Falta uma visão imediata do que exige ação: recebimentos, vencimentos e processos próximos do prazo.
- Gráficos precisam de melhor hierarquia, legendas e estados sem dados.
- Os filtros ocupam muito espaço e não comunicam claramente o período aplicado.

### 3.4 Criação e edição de protocolo

- Formulário longo, apresentado de uma só vez.
- Dados pessoais, endereço, dados funcionais e requerimento não estão agrupados em etapas visuais claras.
- Campos obrigatórios não são suficientemente destacados.
- Falta feedback visual consistente para busca por matrícula e CEP.
- Erros precisam aparecer junto ao campo correspondente.
- Ações finais podem ficar distantes durante a rolagem.
- Não existe uma revisão resumida antes da confirmação.

### 3.5 Listagens e relatórios

- Diversos filtros dependem apenas de placeholder e não possuem rótulo permanente ou nome acessível.
- A tabela possui muitas colunas e ações, dificultando leitura e comparação.
- Localização e responsável competem pelo mesmo espaço.
- Três botões por linha tornam a interface ruidosa.
- Em telas pequenas, a navegação e a tabela não oferecem experiência adequada.
- Não há indicação resumida dos filtros aplicados.
- Falta cabeçalho fixo da tabela durante a rolagem.

### 3.6 Detalhes e tramitação

- Status, prazo, localização e próxima ação não recebem prioridade suficiente.
- Informações estão distribuídas em duas colunas com muito espaço vazio.
- Tramitação, histórico e anexos formam uma página extensa.
- O histórico é textual e pouco escaneável.
- Documentos e versões precisam de agrupamento visual mais claro.
- Ações de editar, gerar documento, receber, tramitar e arquivar precisam de hierarquia e contexto.

### 3.7 Suporte

- O formulário de abertura ocupa grande parte da tela, enquanto o acompanhamento fica comprimido.
- A listagem não destaca última resposta, responsável e tempo desde a atualização.
- Estados dos chamados precisam de linguagem e cores padronizadas.
- A criação de chamado pode ser apresentada em modal ou painel lateral.

### 3.8 Configurações

- Identidade visual, usuários, perfis, tipos e setores ficam em uma única página extensa.
- Falta busca e filtragem de usuários.
- Criação e edição de usuários competem com a listagem na mesma tela.
- Não há pré-visualização consolidada da identidade antes de salvar.
- A administração deve ser separada em áreas ou abas claras.

### 3.9 Acessibilidade e feedback

- Faltam rótulos permanentes em alguns filtros.
- Foco de teclado, contraste e áreas clicáveis precisam de revisão global.
- Ícones não devem ser a única indicação de finalidade.
- Status não podem depender apenas de cor.
- Faltam padrões para carregamento, salvamento, sucesso, erro, confirmação e ausência de dados.

## 4. Objetivos de experiência

1. Permitir que um usuário novo compreenda a navegação sem treinamento prévio extenso.
2. Exibir primeiro o que exige decisão ou ação.
3. Reduzir o número de elementos simultâneos nas telas mais complexas.
4. Garantir funcionamento confortável em desktop, notebook, tablet e celular.
5. Preservar integralmente as regras de negócio, permissões, isolamento por cliente e segurança existentes.
6. Criar um sistema visual reutilizável para futuras funcionalidades.

## 5. Direção proposta

### 5.1 Sistema visual global

- Definir variáveis para cores, tipografia, espaçamento, bordas, sombras e estados.
- Usar família tipográfica legível e consistente.
- Estabelecer componentes padrão: título de página, cartão, campo, filtro, tabela, botão, badge, alerta, modal e estado vazio.
- Definir ações primária, secundária, neutra, perigosa e textual.
- Padronizar status com nome, cor e ícone.

### 5.2 Cabeçalho e navegação

- Cabeçalho compacto em uma linha no desktop.
- Logo e nome da organização dimensionados sem distorção.
- Navegação com item ativo claramente indicado.
- Menu pessoal com nome, perfil, organização, configurações e saída.
- Menu móvel por botão, abrindo painel lateral acessível.
- Possibilidade de menu lateral permanente no desktop, caso os testes demonstrem maior eficiência.

### 5.3 Dashboard orientado a tarefas

- Indicadores clicáveis para novos, vencidos, próximos do prazo e aguardando recebimento.
- Área “Exige sua atenção” com processos prioritários.
- Filtros recolhíveis com período atual visível.
- Gráficos com títulos objetivos, legendas e estados vazios.
- Impressão movida para menu secundário.

### 5.4 Formulário de protocolo

- Agrupar em etapas ou seções: requerente, endereço, dados funcionais, requerimento e revisão.
- Indicar obrigatoriedade e formato esperado.
- Fornecer feedback de busca, preenchimento por CEP e validação.
- Manter ações finais visíveis e coerentes.
- Apresentar resumo antes do envio.

### 5.5 Listagens

- Rótulos permanentes nos filtros.
- Filtros avançados recolhíveis e etiquetas removíveis para filtros ativos.
- Número do protocolo como acesso principal aos detalhes.
- Ação principal visível e menu “Mais opções” para ações secundárias.
- Cabeçalho fixo, melhor alinhamento e densidade ajustável.
- No celular, cartões de protocolo em lugar da tabela completa.

### 5.6 Detalhes do protocolo

- Cabeçalho-resumo com número, requerente, status, prazo e localização.
- Próxima ação permitida em destaque.
- Abas: visão geral, tramitação, histórico e documentos.
- Histórico em linha do tempo.
- Documentos agrupados com suas versões.
- Ações destrutivas ou definitivas separadas e confirmadas.

### 5.7 Suporte

- Lista de chamados como conteúdo principal.
- Novo chamado em modal ou painel lateral.
- Exibir status, prioridade, responsável, última interação e tempo decorrido.
- Conversa do chamado em formato de linha do tempo ou mensagens.

### 5.8 Configurações

- Abas: identidade visual, usuários e permissões, setores e tipos de requerimento.
- Pesquisa e filtros na gestão de usuários.
- Criação e edição em modal ou página dedicada.
- Pré-visualização da identidade antes de salvar.

### 5.9 Acessibilidade

- Rótulos associados a todos os campos.
- Navegação integral por teclado.
- Foco visível.
- Contraste conforme WCAG 2.1 AA como referência.
- Alvos de toque adequados para celular.
- Texto e ícone acompanhando estados e ações relevantes.

## 6. Fases de execução

### Fase 0 — Base e proteção

- Confirmar branch e ambiente Railway isolados.
- Criar inventário de rotas e componentes.
- Registrar capturas de referência das telas atuais.
- Manter testes funcionais existentes como rede de segurança.

### Fase 1 — Fundação visual

- Tokens e componentes globais.
- Tipografia, cores, espaçamento e botões.
- Novo cabeçalho e navegação responsiva.
- Padrão de títulos, mensagens e estados vazios.

### Fase 2 — Fluxo operacional principal

- Listagens de protocolos e recebimentos.
- Detalhes, tramitação, histórico e documentos.
- Criação e edição de protocolo.

### Fase 3 — Gestão e acompanhamento

- Dashboard.
- Relatórios.
- Suporte.
- Configurações.

### Fase 4 — Responsividade e acessibilidade

- Desktop, 1366×768, tablet e celular.
- Teclado, foco, contraste, rótulos e leitores de tela.
- Tratamento de textos longos, listas extensas e estados vazios.

### Fase 5 — Homologação

- Executar testes automatizados existentes.
- Testes visuais e funcionais em todos os perfis.
- Validar dois setores e mais de um cliente.
- Registrar correções e evidências.
- Somente após aceite decidir promoção para desenvolvimento principal e produção.

## 7. Critérios de aceite

- Nenhuma regressão nos 53 testes automatizados atualmente aprovados.
- Menu utilizável sem rolagem horizontal indevida em 375 px de largura.
- Todas as ações essenciais disponíveis por teclado.
- Campos com rótulos e mensagens de erro compreensíveis.
- Tabelas substituídas ou adaptadas adequadamente no celular.
- Status, prazos, localização e próxima ação identificáveis rapidamente.
- Tempos de carregamento e funcionamento preservados.
- Nenhuma quebra de isolamento entre clientes ou de permissões.
- Aprovação visual e operacional antes de qualquer promoção.

## 8. Registro de decisões e progresso

Cada etapa deverá ser registrada abaixo com data, decisão, telas afetadas, testes realizados e pendências.

### 18/09/2026 — diagnóstico inicial

- Revisadas as telas de login, dashboard, novo protocolo, listagem, detalhes, suporte, relatórios e configurações.
- Confirmados problemas de consistência, densidade, hierarquia e responsividade.
- Definida a estratégia de trabalho em ambiente visual isolado.

## 9. Regra de promoção

Nenhuma alteração desta iniciativa será enviada automaticamente para `development` ou `main`. A promoção dependerá de:

1. conclusão da fase correspondente;
2. testes automatizados aprovados;
3. validação visual no navegador;
4. homologação pelo responsável;
5. autorização explícita para promover.
