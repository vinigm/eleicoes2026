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

- **Cores:** Lula vermelho, Flávio azul (convenção dos partidos); branco/nulo e abstenção em cinzas.
  - O validador de paleta reprova os cinzas no "chroma" por definição (são cinzas de propósito).
  - A separação entre vizinhos passa (daltonismo ΔE ≥ 15,9; visão normal ≥ 17,4, claro e escuro).
  - Os cinzas claros têm contraste < 3:1, compensado com legenda, rótulos e tabela em todo gráfico.
- **Mapa:** divergente azul ↔ vermelho centrado em 50% (vencedor); avanço de Lula em rampa sequencial; comparecimento divergente laranja ↔ violeta, para não confundir com as cores dos partidos.
- **Toda frase com número é gerada a partir de `dados.js`** (nada digitado à mão), para não divergir quando os dados forem regenerados.
- Modo claro/escuro (automático + botão); tabela equivalente para cada gráfico; dica no mouse e no foco do teclado.
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
