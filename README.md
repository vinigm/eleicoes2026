# Eleições 2026 · Presidente — 1º × 2º turno

Como o voto para presidente mudou do 1º turno (04/10/2026) para o 2º turno (25/10/2026), por região, estado e município, e para onde foram os eleitores dos candidatos eliminados.

**Página interativa:** https://vinigm.github.io/eleicoes2026/ (código em [`docs/`](docs/))

## Principais resultados

- **Houve virada.** Lula foi de **45,16%** no 1º turno para **51,79%** dos votos válidos no 2º; Flávio Bolsonaro, de **47,03%** para **48,21%**.
- **Minas Gerais foi o único estado que virou** (Flávio no 1º turno, Lula no 2º).
- **O comparecimento subiu** de 78,92% para 80,78%, mas caiu em 9 unidades da federação: os 7 estados do Norte, o Maranhão e o Piauí.
- **Migração de votos (estimativa):** os eleitores de Caiado, Cury e Renan Santos, juntos, se dividiram em cerca de 43–46% para Lula, 35–38% para Flávio e 15–20% em branco ou nulo.
  - A divisão de cada candidato separadamente **não** é robusta. Os detalhes e limites estão na página.

## Dados

- **Fonte:** Tribunal Superior Eleitoral.
- **1º turno:** [dados abertos](https://dadosabertos.tse.jus.br/) (votação por município e zona).
- **2º turno:** arquivos oficiais da [divulgação de resultados](https://resultados.tse.jus.br/), porque o 2º turno ainda não estava nos dados abertos em 26/10/2026.
- **Base final:** 5.571 municípios + 186 cidades do exterior, em [`dados/processados/`](dados/processados/). Os totais nacionais conferem exatamente com o resultado oficial nos dois turnos.

## Como está organizado

| Pasta | Conteúdo |
|---|---|
| [`2026-10-26_base_presidente_1t_2t/`](2026-10-26_base_presidente_1t_2t/) | Coleta, montagem e conferência da base; certificação independente |
| [`2026-10-26_primeira_leitura_regiao_uf/`](2026-10-26_primeira_leitura_regiao_uf/) | Indicadores por Brasil, região e UF |
| [`2026-10-26_inferencia_ecologica/`](2026-10-26_inferencia_ecologica/) | Migração de votos: especificação, implementação e comparação entre duas versões |
| [`2026-10-26_inferencia_ecologica_reimplementacao/`](2026-10-26_inferencia_ecologica_reimplementacao/) | Segunda implementação, escrita de forma independente para conferência |
| [`2026-10-26_html_publico/`](2026-10-26_html_publico/) | Gerador dos dados da página |
| [`docs/`](docs/) | A página |

Cada pasta tem um `README.md` com o contexto, as decisões e os números de referência.

## Como reproduzir

Requer Python 3 com `pandas`, `pyarrow`, `numpy`, `scipy` e `httpx`. Os zips dos dados abertos do TSE não estão no repositório: baixe-os do portal de dados abertos e coloque-os na raiz.

1. `2026-10-26_base_presidente_1t_2t/`: `01_coletar_json_2t.py` → `02_montar_base.py` → `03_conciliar.py`
2. `python3 2026-10-26_primeira_leitura_regiao_uf/leitura_regiao_uf.py`
3. `python3 2026-10-26_inferencia_ecologica/01_estimar_transferencias.py`
4. `python3 2026-10-26_html_publico/gerar_dados_html.py`

## Limites

- **A migração de votos é estimativa estatística (inferência ecológica), não contagem.** O voto é secreto; o modelo deduz o comportamento dos grupos a partir das diferenças entre municípios.
- **As estimativas por região são instáveis** e aparecem na página com aviso.
- **O 2º turno está disponível só por município.** Quando o TSE publicar os dados abertos do 2º turno, a base será reconciliada com eles.
