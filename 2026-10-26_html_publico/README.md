# HTML público — Presidente 2026, 1º × 2º turno

Criado em 26/10/2026. Pasta datada: o gerador é regenerável; o contexto abaixo não.

## O que é

- Página única para publicar no GitHub Pages: `docs/index.html` + `docs/dados.js` + `docs/municipios.js` (cidades, ~430 KB, à parte para não pesar o `dados.js`).
- Seções, na ordem da história (26/10/2026, pedido do Vinicius): resumo, resultado nacional, regiões e estados (mapa em mosaico), saldo do 2º turno, migração de votos (inferência ecológica), conclusão (de onde vieram os votos a mais de Lula) e cidades.
- **O HTML não calcula nada de dado eleitoral.** Ele só lê `docs/dados.js`, gerado aqui a partir de saídas já conferidas:
  - `2026-10-26_primeira_leitura_regiao_uf/indicadores_*.csv`;
  - `2026-10-26_inferencia_ecologica/transferencias.csv` (implementação A; idêntica à B nas estimativas pontuais);
  - `dados/processados/presidente_municipio_turnos.parquet` (só para o % de Caiado por UF).
- A conclusão (`conclusao` em `dados.js`) também é montada no gerador, a partir de `transferencias.csv` (Brasil, E1–E3) e dos indicadores por região.

## Como regenerar

1. `python3 -I 2026-10-26_primeira_leitura_regiao_uf/leitura_regiao_uf.py`
2. `python3 -I 2026-10-26_html_publico/gerar_dados_html.py` → grava `docs/dados.js`
3. Abrir `docs/index.html` direto no navegador (funciona sem servidor).

## Decisões de design

- **Resumo executivo no topo (26/10/2026, pedido do Vinicius):**
  - 5 big numbers do Brasil: Lula, Flávio, vantagem de Lula, comparecimento, brancos e nulos.
    - O número grande é o percentual do 2º turno, e o absoluto vem embaixo, menor (pedido do Vinicius). Depois vêm o 1º turno e a variação, primeiro em pontos e depois em mi.
    - A vantagem de Lula aparece em pontos, com 1 casa decimal (+3,6). Com 2 casas daria 3,57, que pareceria erro diante de 51,79% − 48,21% = 3,58 (é arredondamento).
  - Embaixo, 5 cartões por região: vencedor (ou "virou"), % de Lula e de Flávio no 2º turno com ▲▼ em pontos e em votos, e a barra do 2º turno.
  - O exterior fica fora dos cartões; ele está no mapa.
  - A dica de cada cartão é uma tabela 1º × 2º × diferença com os números exatos. A dos cartões de região é a mesma do mapa.
  - A grade fica sem órfão: 5 por linha em telas largas, 3 + 2 nas médias, 2 nas pequenas e 1 no celular.
- **Resultado nacional (26/10/2026):** cartão com 1º turno à esquerda e 2º à direita, cada um com uma barra de composição dos votos válidos e uma tabela.
  - As linhas ficam na mesma ordem nos dois lados, para comparar lado a lado.
  - Os eliminados aparecem como "—" no 2º turno.
  - Os votos de cada candidato vêm de `votos_1t_por_candidato` em `dados.js`. O gerador confere que a soma fecha com os válidos.
  - Paleta de Cury, Renan, Caiado e "Outros" validada: passa nos dois modos. No claro, o verde e o amarelo ficam abaixo de 3:1 de contraste, compensado pela tabela.
- **Cores:** Lula vermelho, Flávio azul (convenção dos partidos); branco/nulo e abstenção em cinzas.
  - O validador de paleta reprova os cinzas no "chroma" por definição (são cinzas de propósito).
  - A separação entre vizinhos passa (daltonismo ΔE ≥ 15,9; visão normal ≥ 17,4, claro e escuro).
  - Os cinzas claros têm contraste < 3:1, compensado com legenda, rótulos e tabela em todo gráfico.
- **Mapa:** divergente azul ↔ vermelho centrado em 50% (vencedor); avanço de Lula em rampa sequencial; comparecimento divergente laranja ↔ violeta, para não confundir com as cores dos partidos.
- **Toda frase com número é gerada a partir de `dados.js`** (nada digitado à mão), para não divergir quando os dados forem regenerados.
- Modo claro/escuro (automático + botão); tabela equivalente para cada gráfico; dica no mouse e no foco do teclado.
- **Regiões e estados num cartão só (26/10/2026, pedido do Vinicius):** botões "Mostrar por: Regiões | Estados"; Regiões é o padrão e vem primeiro.
  - **Só o mapa do 2º turno**, com ▲▼ desde o 1º em cada quadrado, porque a dica traz os dois turnos. Saíram o mapa do 1º turno, as tabelas embaixo dos mapas e as tabelas completas recolhidas. Pedido do Vinicius: "fica muito poluído".
  - O subtítulo conta as vitórias no 2º turno, com as do 1º entre parênteses.
  - Layout (pedido do Vinicius): no desktop, uma coluna à esquerda traz os filtros empilhados (Indicador, Mostrar por), a legenda de cores, o placar de vitórias e o aviso de uso. O mapa fica sozinho à direita. No celular, tudo isso fica acima do mapa.
  - O aviso de uso "Passe o mouse (ou toque) em uma região/um estado para ver os detalhes" (pedido do Vinicius): os números estão todos na dica.
  - Em "Regiões", os quadrados de cada região viram um bloco único com um rótulo (nome, número, variação e "virou").
  - O mapa fica centralizado no cartão nos dois níveis (pedido do Vinicius). Em "Estados", o contorno marca o estado que virou, e os destaques "O que chama atenção" ficam embaixo do mapa.
  - Nos blocos de região, uma tira de 1 px na cor do quadrado cobre a linha clara que o arredondamento de pixels abria entre quadrados da mesma região.
  - O antigo cartão "Regiões" saiu: repetia a tabela por região.
- **Variação nos mapas (26/10/2026, pedido do Vinicius):** no 2º turno, cada quadrado leva ▲▼ (pontos desde o 1º turno) num selo de fundo neutro, para o ▼ vermelho ser legível em qualquer cor.
  - Fato verificado em 26/10/2026: a vantagem de Lula sobre Flávio subiu nas 27 UFs (de +2,3 pontos em RO a +7,4 no RJ).
- **Legenda dos mapas:** só a barra de cores com as marcas; os textos explicativos saíram (pedido do Vinicius).
- **Versão do `dados.js` no HTML (26/10/2026):** o gerador grava `dados.js?v=<SHA-256 do conteúdo>` no `index.html`.
  - Por quê: o GitHub Pages manda o navegador guardar os arquivos por 10 minutos (`max-age=600`). Depois de um envio, quem já tinha aberto a página recebeu o HTML novo com o `dados.js` antigo, e a página parou no 1º turno do resultado.
  - Reproduzido localmente: dava `Cannot read properties of undefined (reading '13')`.
  - **Regra:** sempre regenerar `docs/` pelo gerador; nunca editar o `dados.js` à mão.
- **Base dos percentuais (26/10/2026, pedido do Vinicius):** botão "Votos válidos" ↔ "Todo o eleitorado" no cartão do resultado nacional. Já esteve também em regiões e estados, mas saiu de lá junto com as tabelas.
  - Na visão eleitorado entram os grupos Lula, Flávio, Outros, Branco/nulo e Abstenção ("não votou" inclui seções não instaladas). Eles somam 100% dos aptos em cada turno, então as variações ▲▼ somam zero: é saldo, não fluxo.
  - Link direto: `#base=eleitorado`.
- **Dicas com quantidades absolutas:** passar o mouse sobre um percentual mostra, nesta ordem, 1º turno, 2º turno e diferença (pedido do Vinicius), e a base do percentual nos dois turnos.
  - Quando votos e percentual andam em sentidos opostos, a dica explica. Exemplo de Sergipe: Flávio ganhou 15.515 votos (+3,7%), mas os válidos cresceram 4,3%, e o percentual caiu 0,16 ponto.
  - Desde 26/10/2026, pedido do Vinicius, essas dicas são uma tabela 1º turno × 2º turno × diferença, com a coluna do turno em destaque. Vale para os mapas (Lula, Flávio, vantagem, comparecimento), as tabelas (votos, base, %) e o resultado nacional do 2º turno.
  - Nos mapas, a tabela tem dois blocos, também a pedido do Vinicius: "Percentuais" e "Em números" (votos de Lula e de Flávio, válidos, compareceram, aptos). No celular ela fica compacta: mede 337 px no Sudeste, numa tela de 390 px.
- **Tela parada ao trocar filtro:** `executarSemPular` compensa a rolagem para o controle clicado ficar no mesmo lugar. Vale para a base, o mapa e o recorte, e a ancoragem automática do navegador foi desligada para não somar duas correções.
  - Testado em 26/10/2026: os cinco controles ficam no mesmo pixel.
- **Largura e rolagem lateral:**
  - a página vai até 1.440 px;
  - abaixo de 1.280 px, os textos das tabelas quebram linha;
  - abaixo de 820 px, as tabelas completas viram fichas (rótulo e valor);
  - na visão eleitorado, a barra fina some abaixo de 1.280 px.
  - Medido em 26/10/2026, em 1.440, 1.280, 1.024, 768 e 390 px, nas duas bases: nenhuma tabela rola para o lado.
- **Poda de texto (26/10/2026, pedido do Vinicius):**
  - saíram a seção de metodologia, o parágrafo de abertura, os subtítulos explicativos das seções e cartões, os rodapés dos cartões e o quadro "Como ler";
  - o aviso de instabilidade ficou em uma linha;
  - a frase "nos três modelos…" virou um gráfico de faixas, que depois saiu (ver abaixo);
  - a metodologia completa continua no repositório (READMEs, `ESPECIFICACAO.md`, `COMPARACAO_A_B.md`).
- **Cartões removidos da seção de migração (26/10/2026, pedido do Vinicius):**
  - "Quanto a estimativa muda conforme o modelo" (sensibilidade, com etiquetas estável/frágil/no limite) e a tabela da estimativa com IC 95%;
  - "De onde veio o crescimento de cada candidato" (faixas entre modelos), que repetia a conclusão.
  - A incerteza continua visível na dica do Sankey (IC 95% e faixa entre os 3 modelos) e nas faixas da conclusão. Os números completos ficam nos CSVs do repositório.
- **Variação negativa em vermelho (26/10/2026, pedido do Vinicius):** todo ▼ (tabelas e dicas) usa `--texto-negativo` (#c62828 no claro, #ff8a80 no escuro).
  - É um vermelho de texto, diferente do vermelho de Lula nas barras, e sempre vem junto da seta ▼.
- **Variação explícita no 2º turno (26/10/2026, pedido do Vinicius):** na tabela do resultado, cada número do 2º turno leva embaixo a diferença para o 1º (▲▼ em pontos percentuais; votos em milhões).
  - O 1º turno reserva uma linha invisível do mesmo tamanho, para os dois lados casarem linha a linha. Com os painéis empilhados (< 820 px), ela some.
  - O rodapé avisa que parte do avanço dos dois vem de o 2º turno ter só dois candidatos.
- **Saldo do 2º turno (26/10/2026):** cartão no mesmo estilo do resultado nacional, com "origem do saldo" e "destino do saldo" lado a lado (barra + tabela).
  - As duas colunas fecham em 14.098.232 votos.
  - O painel é gerado pela função genérica `renderizarPainelComposicao`, reaproveitável nas próximas seções.
- **Mapa dos estados:**
  - **Métrica:** vantagem de Lula sobre Flávio, em pontos (Lula − Flávio nos válidos), na mesma escala divergente ±50 nos dois turnos.
    - O % de Lula não serviria: no 1º turno ele divide os válidos com outros 10 candidatos.
    - Abaixo de 1 ponto, a vantagem mostra casas decimais (Amapá no 1º turno: +0,05).
  - **Botão alternativo:** comparecimento, em rampa sequencial violeta de 72% a 88%. O validador reprova a ponta clara (contraste < 2:1), aceitável em mapa contínuo; todo quadrado ganhou contorno fino para não sumir no fundo.
- **Sankey (26/10/2026):** eleitores dos eliminados (Cury, Renan, Caiado, Outros 7) → Lula, Flávio, branco/nulo e não votou.
  - SVG desenhado à mão, sem biblioteca. Largura da faixa = eleitores estimados; cor = destino.
  - Os grupos Lula, Flávio, branco/nulo e não votou do 1º turno ficaram nas barras, porque seus fluxos (30 a 56 mi) apagariam os dos eliminados.
- **Filtro de recorte** (um seletor): Brasil, 5 regiões e 27 estados.
  - O estado vem de `2026-10-26_migracao_por_uf/transferencias_uf.csv` (implementação A, idêntica à B).
  - Link direto: `#uf=GO` ou `#regiao=Norte`.
  - No estado, os modelos alternativos (na dica do Sankey) são "estado com peso mínimo da região" (κ = 0,25) e "só os demais estados da região" (κ = ∞).
- **`dados.js` tem ~600 KB** por causa das 2.592 linhas por estado (o GitHub Pages serve compactado).
- **Migração por região:** seletor na seção (Brasil é o padrão).
  - Em qualquer região aparece um aviso de instabilidade, montado com números da própria região:
    - municípios;
    - n efetivo de Kish, calculado no gerador a partir de `aptos_1t`;
    - maior município e o peso dele;
    - quantas das 32 frações caíram em 0% ou 100%.
  - Nessa visão, o modelo nacional único aparece como "padrão nacional": nas regiões ele repete o β do Brasil.
  - Link direto para uma região: `index.html#regiao=Centro-Oeste`.

- **Conclusão (26/10/2026, pedido do Vinicius):** "de onde vieram os votos a mais de Lula", no fim da página.
  - Escolhida a **cascata** em vez de um Sankey: o Sankey mostra fluxos, mas não mostra perdas nem fecha num saldo.
  - Cartão 1, Lula × Flávio na mesma escala: eliminados (Cury, Renan, Caiado, outros 7), quem anulou ou não votou, perdas e ajustes → ganho oficial.
    - Cada linha mostra o modelo principal e, embaixo, o menor e o maior valor entre os 3 modelos.
  - Cartão do meio, pedido do Vinicius: Sankey "de que região veio quem anulou ou não votou e foi para Lula".
    - Testou a hipótese "quase tudo veio do Nordeste", que não se confirmou: Sudeste 42% (40–47% entre modelos), Nordeste 31% (29–32%). O Sudeste lidera nos 3 modelos.
    - A taxa é maior no Nordeste: 84% de quem anulou lá foi para Lula, contra 57% no Sudeste. Mas o Sudeste tem mais eleitores.
    - A frase compara só as duas maiores fontes. O Norte (99,6%, IC 77–100%) é instável demais para entrar no texto.
  - Cartão 2, a virada (Lula − Flávio): de −2,22 mi no 1º turno a +4,43 mi no 2º.
    - Rótulos reescritos em 26/10/2026, pedido do Vinicius: "Lula +4,43 mi" era lido como ganho de votos.
    - Agora as pontas dizem "Lula à frente por 4,43 mi", com o placar embaixo, e os passos dizem "puxou 0,78 mi para Lula". O eixo diz "← Flávio à frente · Lula à frente →".
    - 6,09 mi vieram de quem anulou ou não votou.
    - Os eliminados deram só +0,78 mi líquido a Lula (−0,06 a +0,87 entre modelos).
  - As cascatas se adaptam à própria largura (container query), não à da tela. Em 1.024 px, os painéis pela metade ficavam com barras de ~50 px.
  - Identidade: ganho oficial = Σ entradas − perdas + ajuste do modelo + saldo do exterior. O gerador confere em inteiros, nos 6 casos (2 finalistas × 3 modelos).
  - O gerador também confere o ajuste contra real − previsto (tolerância de 6 votos), para ele não virar uma sobra que fecha a conta à força.
  - **Certificação independente (26/10/2026):** reprovou a 1ª versão.
    - Causa: faltava a troca direta entre finalistas (5,2 mil votos Flávio → Lula na E3), que caía dentro do ajuste.
    - Corrigido com a "troca direta" como origem própria; todo o resto conferiu.

- **Perfil das cidades (26/10/2026, pedido do Vinicius):** dois cartões no topo da seção "Cidades".
  - **Mapa de calor "tamanho da cidade × voto":**
    - Linhas: Brasil e regiões, ou cada região seguida dos seus estados (botão Regiões | Estados).
    - Colunas: as 5 faixas de habitantes e "Todas". Cada célula mostra o % de Flávio no 2º turno (votos somados), com a mesma cor do mapa (azul = Flávio, vermelho = Lula) e o número de cidades.
    - A frase de cima é gerada dos dados.
    - **Fato:** Flávio tem 43,9% nas cidades até 50 mil habitantes, o seu pior tamanho, porque 38% de quem mora nelas está no Nordeste. Dentro das regiões o desenho muda. No Nordeste e no Norte, Flávio cresce com o tamanho da cidade. No Sul, vai um pouco melhor nas pequenas e médias. No Sudeste, o pior resultado dele é acima de 300 mil.
  - **Dispersão "índices sociais × voto":** 6 painéis (Brasil e as 5 regiões); cada ponto é uma cidade.
    - Os pontos são cinza e o fundo tem duas faixas: azul-claro acima de 50% ("Flávio venceu") e vermelho-claro abaixo ("Lula venceu").
      - Antes, a cor do ponto era o vencedor e só repetia a altura. Parecia um padrão sem ser (dúvida do Vinicius em 26/10/2026).
      - A legenda diz que o eixo vertical é o % de Flávio e que uma linha subindo quer dizer mais índice, mais voto em Flávio.
    - Índice no eixo x: alfabetização (Censo 2022) ou PIB per capita (2023, escala log). Fonte: `2026-10-26_indicadores_ibge/`.
    - Cada painel tem a reta de mínimos quadrados e o r de Pearson. Cada cidade pesa igual, e o PIB entra em log10.
    - O texto do cartão avisa: os índices medem acesso a estudo e renda, não inteligência; e a relação entre cidades não diz como votou cada eleitor.
    - **Fato:** dentro de todas as regiões, cidades com mais alfabetização e mais PIB per capita deram mais votos a Flávio.
      - Alfabetização: r de +0,20 (Norte) a +0,65 (Sudeste).
      - PIB: r de +0,30 (Sul) a +0,54 (Norte).
      - O r do Brasil (+0,81 em alfabetização) fica inflado pela diferença entre regiões.
    - **Conferência independente (26/10/2026):** aprovada para o heatmap (36 células) e para as regressões.
      - Uma ressalva foi corrigida: a alfabetização era gravada com 1 casa e mudava inclinações na 3ª casa decimal. Agora vai com as 2 casas do IBGE.
- **Cidades (26/10/2026, pedido do Vinicius):** última seção. Tem filtro por estado (ou "Todos os estados", ou "Exterior"), busca por nome sem acento ("sao joao" acha "São João del Rei") e lista ordenável clicando no cabeçalho.
  - Colunas: barra do 2º turno; Lula e Flávio com 1º turno, 2º turno e variação, cada uma com % (ou pontos) em cima e votos embaixo; vantagem e comparecimento (2º turno e ▲▼); eleitores; habitantes (IBGE 2026, ver `2026-10-26_populacao_ibge/`).
  - Entre 820 e 1.279 px saem a barra e a vantagem, para não haver rolagem lateral. Na tabela, a palavra "votos" fica só no cabeçalho ("Lula · % e votos"); nas fichas do celular, aparece em cada número.
  - Não há dica ao passar o mouse nem o card de instrução, a pedido do Vinicius: a linha já mostra tudo.
  - As colunas de Lula têm fundo vermelho claro e as de Flávio, azul claro (pedido do Vinicius: "pra conseguir ver melhor"). O título de cada grupo vem na cor do candidato.
    - O texto continua escuro de propósito: com os números de Lula em vermelho, o ▼ vermelho das quedas sumiria.
    - Tokens: `--fundo-lula`, `--fundo-flavio`, `--cabecalho-*` e `--titulo-*`, com versões para o claro e o escuro.
  - "Virou" aparece num selo vermelho (`--fundo-virou`) aqui, no mapa e nos cartões de região do resumo.
  - A lista mostra 100 cidades por vez (25 no celular, onde cada uma vira uma ficha), com o botão "Mostrar mais". O padrão é ordenar pelo número de eleitores, maior primeiro.
  - Ao lado da busca, um card mostra só Lula x% e Flávio y% no 2º turno, a pedido do Vinicius. A conta soma as cidades do recorte: Brasil, estado, cidades encontradas ou a cidade.
    - Conferido em 26/10/2026: Brasil 51,79/48,21; MG 50,43/49,57; exterior 53,86/46,14; Belo Horizonte 49,20/50,80.
  - Embaixo do card, os botões "Todas · N", "Lula ganhou · N" e "Flávio ganhou · N" filtram a lista pelo vencedor do 2º turno, a pedido do Vinicius.
    - As contagens seguem o recorte (estado e busca); o card de % não muda com esse filtro.
    - "Todas" inclui as 42 cidades sem voto válido e 1 empate, por isso Lula + Flávio dá menos que o total.
    - Conferido: Brasil 2.963 × 2.751; MG 528 × 325.
  - Embaixo dos botões aparecem "Mais petista" e "Mais bolsonarista", a pedido do Vinicius: a cidade com o maior % de Lula e a com o maior % de Flávio no 2º turno, dentro do recorte. Clicar mostra só aquela cidade; clicar de novo volta.
    - O exterior só entra quando "Exterior" está selecionado, e é preciso ter pelo menos 100 votos válidos. Sem essa regra, Havana (44 votos, 97,7% Lula) e Katmandu (13 votos) disputariam.
    - Brasil em 26/10/2026: Carnaubeira da Penha (PE), Lula 92,3%; Nova Pádua (RS), Flávio 90,6%.
  - Os filtros (Estado, Habitantes, Buscar cidade) ficam num painel destacado, com fonte de 17 px e todos com 46 px de altura (pedido do Vinicius: "tá meio perdido"). O `<select>` usa estilo próprio, porque o Safari desenha o nativo miúdo. A busca ficou mais estreita (até 280 px).
  - Seletor "Habitantes" ao lado de "Estado", a pedido do Vinicius, para não comparar só cidades de 2 mil habitantes. Faixas: até 50 mil, 50–100, 100–200, 200–300 e mais de 300 mil, cada uma com a contagem do recorte.
    - A faixa vale para tudo: lista, card de %, placar, botões de vencedor e "mais petista/bolsonarista". O exterior sai, porque não tem população.
    - Fato, 26/10/2026: Lula tem 56,07% nas cidades até 50 mil, cai até 45,87% em 200–300 mil e volta a 50,37% acima de 300 mil.
    - Acima de 300 mil habitantes (98 cidades), a mais petista é Juazeiro do Norte (CE), com 74,0% para Lula; a mais bolsonarista é Boa Vista (RR), com 75,8% para Flávio.
  - O placar no topo vale para o estado escolhido. Exemplo de MG: Lula 528 × Flávio 325 cidades (no 1º turno, 452 × 401).
  - **Dados:** `municipios.js` (`window.DADOS_MUNICIPIOS`, em colunas + linhas), gravado pelo gerador a partir do parquet certificado.
    - O gerador confere que a soma das 5.757 linhas bate com o Brasil nos 10 campos (aptos, comparecimento, válidos e votos de Lula e Flávio, nos dois turnos).
    - O arquivo também é versionado pelo conteúdo (`municipios.js?v=<hash>`).
  - Nomes passados de MAIÚSCULAS para a grafia usual, com conectivos em minúscula ("Olho d'Água das Flores", "São João del Rei", "Embu-Guaçu").
  - 42 cidades do exterior não tiveram voto válido: aparecem com "—" e vão para o fim de qualquer ordenação.
  - Conferido em 26/10/2026 contra o parquet, com cálculo independente: São Paulo, Rio de Janeiro, Brasília, Abadia dos Dourados e o placar de MG batem.

## Verificação feita em 26/10/2026

- Renderizada no Chrome headless em desktop (1200 px), celular (390 px, via iframe) e modo escuro: sem rolagem horizontal, sem erro no console.
- Frases conferidas contra os números em Python (faixas entre modelos, Goiás, quedas de comparecimento).
- **Não verificado:** interação com o mouse (dicas) em navegador real; hospedagem no GitHub Pages.
