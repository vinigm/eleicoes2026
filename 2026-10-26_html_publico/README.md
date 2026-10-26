# HTML público — Presidente 2026, 1º × 2º turno

Criado em 26/10/2026. Pasta datada: o gerador é regenerável; o contexto abaixo não.

## O que é

- Página única para publicar no GitHub Pages: `docs/index.html` + `docs/dados.js`.
- Seções: resultado, origem dos votos a mais, regiões, estados (mapa em mosaico), migração de votos (inferência ecológica) e metodologia.
- **O HTML não calcula nada de dado eleitoral.** Ele só lê `docs/dados.js`, gerado aqui a partir de saídas já conferidas:
  - `2026-10-26_primeira_leitura_regiao_uf/indicadores_*.csv`;
  - `2026-10-26_inferencia_ecologica/transferencias.csv` (implementação A; idêntica à B nas estimativas pontuais);
  - `dados/processados/presidente_municipio_turnos.parquet` (só para o % de Caiado por UF).

## Como regenerar

1. `python3 -I 2026-10-26_primeira_leitura_regiao_uf/leitura_regiao_uf.py`
2. `python3 -I 2026-10-26_html_publico/gerar_dados_html.py` → grava `docs/dados.js`
3. Abrir `docs/index.html` direto no navegador (funciona sem servidor).

## Decisões de design

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
- **Base dos percentuais (26/10/2026, pedido do Vinicius):** botão "Votos válidos" ↔ "Todo o eleitorado", repetido nos cartões de resultado, regiões e estados, mas com uma configuração só (mudar em um muda nos três).
  - Na visão eleitorado entram os grupos Lula, Flávio, Outros, Branco/nulo e Abstenção ("não votou" inclui seções não instaladas). Eles somam 100% dos aptos em cada turno, então as variações ▲▼ somam zero: é saldo, não fluxo.
  - Link direto: `#base=eleitorado`.
- **Dicas com quantidades absolutas:** passar o mouse sobre um percentual das tabelas mostra votos ou pessoas nos dois turnos e a diferença.
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
  - a frase "nos três modelos…" virou o gráfico de faixas "De onde veio o crescimento" (mínimo–máximo entre os modelos + ponto do principal);
  - a metodologia completa continua no repositório (READMEs, `ESPECIFICACAO.md`, `COMPARACAO_A_B.md`).
- **Sensibilidade da migração (26/10/2026):** cartão com "Foi para Lula" e "Foi para Flávio" lado a lado. As linhas são os grupos do 1º turno: os 3 eliminados juntos, Caiado, Cury, Renan, quem votou branco/nulo e quem não votou.
  - Colunas:
    - faixa 0–100% com o principal (ponto cheio), as alternativas (círculos vazados) e o IC 95%;
    - valor principal com o IC embaixo;
    - mínimo–máximo entre os modelos, com a amplitude e uma etiqueta.
  - **Etiquetas:** "estável" (< 10 pontos), "frágil" (≥ 10) ou "no limite" (principal preso em 0% ou 100%; isso não é estabilidade).
  - Segue o filtro de recorte (Brasil, região ou estado).
- **Variação negativa em vermelho (26/10/2026, pedido do Vinicius):** todo ▼ (tabelas e dicas) usa `--texto-negativo` (#c62828 no claro, #ff8a80 no escuro).
  - É um vermelho de texto, diferente do vermelho de Lula nas barras, e sempre vem junto da seta ▼.
- **Variação explícita no 2º turno (26/10/2026, pedido do Vinicius):** nas tabelas de resultado, regiões e estados, cada número do 2º turno leva embaixo a diferença para o 1º (▲▼ em pontos percentuais; votos em milhões no resultado).
  - Exemplo do Norte: Lula 50,01% ▲ 5,36; Flávio 49,99% ▲ 0,84.
  - O 1º turno reserva uma linha invisível do mesmo tamanho, para os dois lados casarem linha a linha. Com os painéis empilhados (< 820 px), ela some.
  - O rodapé avisa que parte do avanço dos dois vem de o 2º turno ter só dois candidatos.
- **Saldo do 2º turno (26/10/2026):** cartão no mesmo estilo do resultado nacional, com "origem do saldo" e "destino do saldo" lado a lado (barra + tabela).
  - As duas colunas fecham em 14.098.232 votos.
  - O painel é gerado pela função genérica `renderizarPainelComposicao`, reaproveitável nas próximas seções.
- **Regiões (26/10/2026):** cartão com 1º turno à esquerda e 2º à direita. Cada painel é uma tabela com as regiões (mais exterior e total) nas linhas, na mesma ordem dos dois lados.
  - Colunas: barra fina dos votos válidos (Lula / Flávio / outros 10), % de Lula e de Flávio com 2 casas e comparecimento.
  - O vencedor de cada região e turno fica em negrito.
  - Usar 2 casas é necessário: no Norte, o 2º turno foi 50,01% × 49,99%.
  - Substitui os antigos gráficos de halteres e de barras de comparecimento.
  - O rodapé lista as viradas e as quedas de comparecimento a partir dos dados.
- **Estados (26/10/2026):** cartão com 1º turno à esquerda e 2º à direita. Em cada lado, um mapa em mosaico e, embaixo, uma tabela das 27 UFs agrupadas por região (barra fina, % de Lula e Flávio com 2 casas, vencedor em negrito, etiqueta "virou").
  - **Métrica do mapa:** vantagem de Lula sobre Flávio, em pontos (Lula − Flávio nos válidos), na mesma escala divergente ±50 nos dois turnos.
    - O % de Lula não serviria: no 1º turno ele divide os válidos com outros 10 candidatos.
    - Abaixo de 1 ponto, a vantagem mostra casas decimais (Amapá no 1º turno: +0,05).
  - **Botão alternativo:** comparecimento, em rampa sequencial violeta de 72% a 88%. O validador reprova a ponta clara (contraste < 2:1), aceitável em mapa contínuo; todo quadrado ganhou contorno fino para não sumir no fundo.
  - **A tabela de estados não tem comparecimento:** a largura não comporta, e ele está no mapa e na tabela completa.
- **Sankey (26/10/2026):** eleitores dos eliminados (Cury, Renan, Caiado, Outros 7) → Lula, Flávio, branco/nulo e não votou.
  - SVG desenhado à mão, sem biblioteca. Largura da faixa = eleitores estimados; cor = destino.
  - Os grupos Lula, Flávio, branco/nulo e não votou do 1º turno ficaram nas barras, porque seus fluxos (30 a 56 mi) apagariam os dos eliminados.
- **Filtro de recorte** (um seletor): Brasil, 5 regiões e 27 estados.
  - O estado vem de `2026-10-26_migracao_por_uf/transferencias_uf.csv` (implementação A, idêntica à B).
  - Link direto: `#uf=GO` ou `#regiao=Norte`.
  - No estado, a sensibilidade compara "estado com peso mínimo da região" (κ = 0,25) e "só os demais estados da região" (κ = ∞).
- **`dados.js` tem ~600 KB** por causa das 2.592 linhas por estado (o GitHub Pages serve compactado).
- **Migração por região:** seletor na seção (Brasil é o padrão).
  - Em qualquer região aparece um aviso de instabilidade, montado com números da própria região:
    - municípios;
    - n efetivo de Kish, calculado no gerador a partir de `aptos_1t`;
    - maior município e o peso dele;
    - quantas das 32 frações caíram em 0% ou 100%.
  - Nessa visão, o modelo nacional único aparece como "padrão nacional": nas regiões ele repete o β do Brasil.
  - Link direto para uma região: `index.html#regiao=Centro-Oeste`.

## Verificação feita em 26/10/2026

- Renderizada no Chrome headless em desktop (1200 px), celular (390 px, via iframe) e modo escuro: sem rolagem horizontal, sem erro no console.
- Frases conferidas contra os números em Python (faixas entre modelos, Goiás, quedas de comparecimento).
- **Não verificado:** interação com o mouse (dicas) em navegador real; hospedagem no GitHub Pages.
